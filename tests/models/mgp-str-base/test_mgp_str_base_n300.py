# SPDX-FileCopyrightText: (c) 2024 Tenstorrent AI ULC
#
# SPDX-License-Identifier: Apache-2.0
# From: https://huggingface.co/alibaba-damo/mgp-str-base

from PIL import Image
import requests
import torch
from transformers import MgpstrProcessor, MgpstrForSceneTextRecognition
import pytest
from tests.utils import ModelTester
from tt_torch.tools.utils import CompilerConfig, CompileDepth, OpByOpBackend


class ThisTester(ModelTester):
    def _load_model(self):
        model = MgpstrForSceneTextRecognition.from_pretrained(
            "alibaba-damo/mgp-str-base", torch_dtype=torch.bfloat16
        )
        self.processor = MgpstrProcessor.from_pretrained(
            "alibaba-damo/mgp-str-base", torch_dtype=torch.bfloat16
        )
        return model

    def _load_inputs(self):
        url = "https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/ocr-demo.png"  # generated_text = "ticket"
        image = Image.open(requests.get(url, stream=True).raw).convert("RGB")
        images = [image] * 16  # Create a batch of 16
        inputs = self.processor(
            images=images,
            return_tensors="pt",
        )
        inputs["pixel_values"] = inputs["pixel_values"].to(torch.bfloat16)
        return inputs


@pytest.mark.parametrize(
    "mode",
    ["train", "eval"],
)
@pytest.mark.parametrize(
    "op_by_op",
    [OpByOpBackend.STABLEHLO, OpByOpBackend.TORCH, None],
    ids=["op_by_op_stablehlo", "op_by_op_torch", "full"],
)
def test_mgp_str_base(record_property, mode, op_by_op):
    if mode == "train":
        pytest.skip()
    model_name = "alibaba-damo/mgp-str-base"

    cc = CompilerConfig()
    cc.enable_consteval = True
    cc.consteval_parameters = True
    cc.automatic_parallelization = True
    cc.mesh_shape = [1, 2]
    cc.dump_debug = True
    if op_by_op:
        cc.compile_depth = CompileDepth.EXECUTE_OP_BY_OP
        if op_by_op == OpByOpBackend.STABLEHLO:
            cc.op_by_op_backend = OpByOpBackend.STABLEHLO

    # TODO Enable checking - https://github.com/tenstorrent/tt-torch/issues/552
    disable_checking = True

    tester = ThisTester(
        model_name,
        mode,
        relative_atol=0.02,
        compiler_config=cc,
        record_property_handle=record_property,
        assert_pcc=True,
        assert_atol=False
        if disable_checking
        else True,  # ATOL checking issues - No model legitimately checks ATOL, issue #690
    )
    results = tester.test_model()

    if mode == "eval" and not disable_checking:
        logits = results.logits
        generated_text = tester.processor.batch_decode(logits)["generated_text"]
        print(f"Generated text: '{generated_text}'")
        assert generated_text[0] == "ticket"

    tester.finalize()

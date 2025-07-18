# SPDX-FileCopyrightText: (c) 2024 Tenstorrent AI ULC
#
# SPDX-License-Identifier: Apache-2.0
# Reference: https://huggingface.co/state-spaces/mamba-2.8b-hf

from transformers import MambaForCausalLM, AutoTokenizer, GenerationConfig
import pytest
from tests.utils import ModelTester
from tt_torch.tools.utils import CompilerConfig, CompileDepth, OpByOpBackend
import torch


class ThisTester(ModelTester):
    def _load_model(self):
        model = MambaForCausalLM.from_pretrained(
            self.model_name, torch_dtype=torch.bfloat16
        )

        model.generate = lambda **kwargs: type(model).generate(
            model, **{**kwargs, "use_cache": False}
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, torch_dtype=torch.bfloat16
        )

        return model

    def _load_inputs(self):
        prompt = "Hey how are you doing?"
        input_ids = self.tokenizer(prompt, return_tensors="pt")["input_ids"]
        generation_config = GenerationConfig(max_new_tokens=10, use_cache=False)
        arguments = {
            "input_ids": input_ids,
            "generation_config": generation_config,
            "use_cache": False,
        }
        return arguments


@pytest.mark.parametrize(
    "mode",
    ["eval"],
)
@pytest.mark.parametrize(
    "model_name",
    [
        "state-spaces/mamba-790m-hf",
        "state-spaces/mamba-2.8b-hf",
        "state-spaces/mamba-1.4b-hf",
        "state-spaces/mamba-370m-hf",
    ],
)
@pytest.mark.parametrize(
    "op_by_op",
    [OpByOpBackend.STABLEHLO, OpByOpBackend.TORCH, None],
    ids=["op_by_op_stablehlo", "op_by_op_torch", "full"],
)
def test_mamba(record_property, model_name, mode, op_by_op):

    cc = CompilerConfig()
    if op_by_op:
        cc.compile_depth = CompileDepth.EXECUTE_OP_BY_OP
        if op_by_op == OpByOpBackend.STABLEHLO:
            cc.op_by_op_backend = OpByOpBackend.STABLEHLO

    tester = ThisTester(
        model_name,
        mode,
        compiler_config=cc,
        record_property_handle=record_property,
        run_generate=False,
        required_pcc=0.95,
        assert_atol=False,
    )

    results = tester.test_model()

    if mode == "eval":
        logits = results.logits if hasattr(results, "logits") else results[0]
        token_ids = torch.argmax(logits, dim=-1)
        gen_text = tester.tokenizer.batch_decode(token_ids, skip_special_tokens=True)
        print("Generated text: ", gen_text)

    tester.finalize()

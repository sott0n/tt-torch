# SPDX-FileCopyrightText: (c) 2024 Tenstorrent AI ULC
#
# SPDX-License-Identifier: Apache-2.0
# Reference: https://github.com/tenstorrent/tt-buda-demos/blob/main/model_demos/cv_demos/openpose/pytorch_lwopenpose_2d_osmr.py

import torch
from PIL import Image
from pytorchcv.model_provider import get_model as ptcv_get_model
from torchvision import transforms
import pytest
from tests.utils import ModelTester
from tt_torch.tools.utils import CompilerConfig, CompileDepth, OpByOpBackend
from third_party.tt_forge_models.tools.utils import get_file


def get_image_tensor():
    # Image processing
    image_file = get_file(
        "https://raw.githubusercontent.com/axinc-ai/ailia-models/master/pose_estimation_3d/blazepose-fullbody/girl-5204299_640.jpg"
    )
    input_image = Image.open(str(image_file))
    preprocess = transforms.Compose(
        [
            transforms.Resize(224),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    input_tensor = preprocess(input_image)
    input_batch = input_tensor.unsqueeze(
        0
    )  # create a mini-batch as expected by the model
    return input_batch


class ThisTester(ModelTester):
    def _load_model(self):
        # Create PyBuda module from PyTorch model
        model = ptcv_get_model("lwopenpose2d_mobilenet_cmupan_coco", pretrained=True)
        model = model.to(torch.bfloat16)
        return model

    def _load_inputs(self):
        input_batch = [get_image_tensor()]
        batch_input = torch.cat(input_batch, dim=0)
        batch_input = batch_input.to(torch.bfloat16)
        return batch_input


@pytest.mark.parametrize(
    "mode",
    ["train", "eval"],
)
@pytest.mark.parametrize(
    "op_by_op",
    [OpByOpBackend.STABLEHLO, OpByOpBackend.TORCH, None],
    ids=["op_by_op_stablehlo", "op_by_op_torch", "full"],
)
def test_openpose_v2(record_property, mode, op_by_op):
    if mode == "train":
        pytest.skip()
    model_name = "OpenPose V2"

    cc = CompilerConfig()
    cc.enable_consteval = True
    cc.consteval_parameters = True
    if op_by_op:
        cc.compile_depth = CompileDepth.EXECUTE_OP_BY_OP
        if op_by_op == OpByOpBackend.STABLEHLO:
            cc.op_by_op_backend = OpByOpBackend.STABLEHLO

    tester = ThisTester(
        model_name,
        mode,
        assert_pcc=False,
        assert_atol=False,
        compiler_config=cc,
        record_property_handle=record_property,
    )
    results = tester.test_model()
    if mode == "eval":
        print(f"Output: {results}")

    tester.finalize()

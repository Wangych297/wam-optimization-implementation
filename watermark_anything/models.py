# Copyright (c) Meta Platforms, Inc. and affiliates.
# Original: https://github.com/facebookresearch/watermark-anything
# Reconstructed from upstream module interfaces for local reproducibility.

import torch
import torch.nn as nn

from watermark_anything.modules.vae import VAEEncoder, VAEDecoder
from watermark_anything.modules.msg_processor import MsgProcessor
from watermark_anything.modules.vit import ImageEncoderViT
from watermark_anything.modules.pixel_decoder import PixelDecoder


def build_embedder(model_name: str, params: dict, nbits: int):
    msg_cfg = params["msg_processor"]
    if msg_cfg["nbits"] != nbits:
        hidden_size = nbits * 2
        msg_cfg = dict(msg_cfg, nbits=nbits, hidden_size=hidden_size)
        decoder_cfg = dict(params["decoder"])
        decoder_cfg["z_channels"] = params["encoder"]["z_channels"] + hidden_size
        decoder = VAEDecoder(**decoder_cfg)
    else:
        decoder = VAEDecoder(**params["decoder"])
    msg_processor = MsgProcessor(**msg_cfg)

    encoder = VAEEncoder(**params["encoder"])

    return WamEmbedder(encoder, msg_processor, decoder)


def build_extractor(model_name: str, params: dict, img_size: int, nbits: int):
    encoder_cfg = dict(params["encoder"])
    decoder_cfg = dict(params["pixel_decoder"])
    if decoder_cfg["nbits"] != nbits:
        decoder_cfg = dict(decoder_cfg, nbits=nbits)

    image_encoder = ImageEncoderViT(**encoder_cfg)
    pixel_decoder = PixelDecoder(**decoder_cfg)

    return WamExtractor(image_encoder, pixel_decoder)


class WamEmbedder(nn.Module):
    def __init__(self, encoder, msg_processor, decoder):
        super().__init__()
        self.encoder = encoder
        self.msg_processor = msg_processor
        self.decoder = decoder

    def forward(self, image, msg):
        latents = self.encoder(image)
        latents_msg = self.msg_processor(latents, msg)
        deltas = self.decoder(latents_msg)
        return deltas


class WamExtractor(nn.Module):
    def __init__(self, image_encoder, pixel_decoder):
        super().__init__()
        self.image_encoder = image_encoder
        self.pixel_decoder = pixel_decoder

    def forward(self, image):
        features = self.image_encoder(image)
        preds = self.pixel_decoder(features)
        return preds


class Wam(nn.Module):
    def __init__(self, embedder, detector, augmenter, attenuation, scaling_w, scaling_i):
        super().__init__()
        self.embedder = embedder
        self.detector = detector
        self.augmenter = augmenter
        self.attenuation = attenuation
        self.scaling_w = scaling_w
        self.scaling_i = scaling_i

    def embed(self, image, msg):
        deltas = self.embedder(image, msg)
        imgs_w = self.scaling_i * image + self.scaling_w * deltas
        return {"imgs_w": imgs_w, "deltas": deltas}

    def detect(self, image):
        preds = self.detector(image)
        return {"preds": preds}

    def forward(self, image, msg, mask=None):
        outputs = self.embed(image, msg)
        img_w = outputs["imgs_w"]
        if mask is not None:
            img_w = img_w * mask + image * (1 - mask)
        preds = self.detect(img_w)
        return {"imgs_w": img_w, "deltas": outputs["deltas"], "preds": preds["preds"]}

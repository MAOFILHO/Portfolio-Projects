# MobileNet-SSD (Caffe)

Pretrained weights for a MobileNet-SSD object detector, trained on PASCAL VOC
(20 classes + background). Sourced from
[SaiSubhakarT/Doorway-Traffic-Counter](https://github.com/SaiSubhakarT/Doorway-Traffic-Counter)
(MIT License), which itself packages the widely-used
`MobileNetSSD_deploy` Caffe model originally published alongside chuanqi305's
`MobileNet-SSD` project.

Used by `surveil_core.ssd_analyzer.SsdMobileNetAnalyzer` as a self-hosted,
no-Azure-cost alternative to `AzureVisionAnalyzer` — see
`docs/extending-phase2.md` for why this exists and its tradeoffs (20 fixed
VOC classes, no caption support, CPU-only inference).

No training happened in this project — these are the original pretrained
weights, used as-is for inference.

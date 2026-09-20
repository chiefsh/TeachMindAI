# 宏观实验剧本

`generate.py` 的 `build_*` 返回一份 JSON，注入 `template/lab.html` 的 `__LAB_DATA__`。
生成时内联 `lab2d.js`，页面自包含。

必填：`id`、`scene`（`oxygen` | `gas_wet` | `gas_air` | `burn` | `neutralization` | `electrolysis` | `filtration` | `evaporation` | `oxide`）、`title`、`inventory`、`required_apparatus`、`required_reagents`、`steps`、`complete`。

可选 `scene_init`：进入实验台时的场景开关。

`inventory.*.slot` 由 `generate.py` 的 `with_slots` 自动填写：所需器材的工位名等于器材 `id`，所需药品工位为 `reagent`，干扰项 `slot` 为空（拖上台面会失败）。

`steps[].need`：

- `select`：从画布左上角把器材拖到同形虚线工位、药品拖到「药品」虚线；全部放对后自动进入下一步
- `choice`：二选一/三选一，`choices[].correct` 为真才进入下一步；错选记安全事故
- `action`：点一次操作按钮，写入 `phenomenon`，可带 `scene` 开关

场景开关（oxygen 制气台）：`powder` / `zinc` / `marble` / `acid` / `flame` / `no_lamp` / `upright` / `air_collect` / `bubbles` / `collected` / `splint_on` / `pop` / `jet_flame` / `sparks` / `bottle_water` / `wet_paper` / `lime` / `lime_milky`。
场景开关（neutralization 烧杯）：`goggles` / `liquid=clear|pink|pale` / `dripping` / `metal` / `acid_bubbles` / `done`。
场景开关（electrolysis）：`gases` / `ratio`。
场景开关（filtration）：`paper` / `drain` / `residue` / `filtrate`。
场景开关（evaporation）：`heat` / `stir` / `crystals`。

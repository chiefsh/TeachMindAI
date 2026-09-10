# 宏观实验剧本

`generate.py` 的 `build_*` 返回一份 JSON，注入 `template/lab.html` 的 `__LAB_DATA__`。

必填：`id`、`scene`（`oxygen` | `neutralization` | `electrolysis` | `filtration` | `evaporation`）、`title`、`inventory`、`required_apparatus`、`required_reagents`、`steps`、`complete`。

可选 `scene_init`：进入实验台时的场景开关。

`steps[].need`：

- `select`：点选器材与药品，必须覆盖 required 列表
- `choice`：二选一/三选一，`choices[].correct` 为真才进入下一步；错选记安全事故
- `action`：点一次操作按钮，写入 `phenomenon`，可带 `scene` 开关

场景开关（oxygen 制气台）：`powder` / `zinc` / `marble` / `acid` / `flame` / `no_lamp` / `upright` / `air_collect` / `bubbles` / `collected` / `splint_on` / `pop` / `jet_flame` / `sparks` / `bottle_water` / `wet_paper` / `lime` / `lime_milky`。
场景开关（neutralization 烧杯）：`goggles` / `liquid=clear|pink|pale` / `dripping` / `metal` / `acid_bubbles` / `done`。
场景开关（electrolysis）：`gases` / `ratio`。
场景开关（filtration）：`paper` / `drain` / `residue` / `filtrate`。
场景开关（evaporation）：`heat` / `stir` / `crystals`。

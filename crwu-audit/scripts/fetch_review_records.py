#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段二：按阶段一排除清单定向取回复核记录（只读守卫 + 留痕）。

纪律：
- **只接受显式 fileId 清单**（= 阶段一 allowlist 排除时落盘的清单），不现编、不猜测；
- 落 `<案例>/复核-人工/`，**禁止写入 `材料-源/`**；
- 逐件校验字节数，不符即记失败、不落盘；
- 写 `.fetch-manifest.json` 留痕（来源清单、逐件大小、失败原因）。

用法：
    python3 scripts/fetch_review_records.py --case <案例目录> \\
        --manifest <排除清单.json> --source <阶段一下载全集目录>
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description="阶段二按清单取回复核记录（只读守卫 + 留痕）")
    ap.add_argument("--case", required=True)
    ap.add_argument("--manifest", required=True, help="阶段一排除清单 JSON：[{fileId,name,sizeBytes}, …]")
    ap.add_argument("--source", required=True, help="阶段一下载全集目录（复核件被排除但文件仍在其内）")
    ap.add_argument("--out", default=None, help="落盘目录（默认 <案例>/复核-人工）")
    args = ap.parse_args()

    case = os.path.abspath(args.case)
    source = os.path.abspath(args.source)
    out = os.path.abspath(args.out or os.path.join(case, "复核-人工"))
    src_materials = os.path.join(case, "材料-源")

    if out == src_materials or out.startswith(src_materials + os.sep):
        print(f"error: 复核件落盘目录不得在材料-源内：{out}")
        return 2
    if not os.path.isdir(source):
        print(f"error: 阶段一源目录不存在：{source}")
        return 2

    manifest = json.loads(open(args.manifest, encoding="utf-8").read())
    if not isinstance(manifest, list):
        print("error: 清单必须是数组 [{fileId,name,sizeBytes}, …]")
        return 2

    os.makedirs(out, exist_ok=True)
    results = []
    for entry in manifest:
        file_id = entry.get("fileId")
        name = entry.get("name")
        size = entry.get("sizeBytes")
        if not file_id or not name:
            results.append({"fileId": file_id, "name": name, "ok": False,
                            "reason": "清单项缺 fileId/name"})
            continue
        candidate = os.path.join(source, name)
        rec = {"fileId": file_id, "name": name, "ok": False}
        if not os.path.isfile(candidate):
            rec["reason"] = f"阶段一源目录内未找到：{name}"
        else:
            actual = os.path.getsize(candidate)
            if size is not None and actual != int(size):
                rec["reason"] = f"字节数不符（清单 {size} / 实际 {actual}），拒绝落盘"
            else:
                dst = os.path.join(out, name)
                with open(candidate, "rb") as fin, open(dst, "wb") as fout:
                    fout.write(fin.read())
                rec["ok"] = True
                rec["localPath"] = dst
                rec["sizeBytes"] = os.path.getsize(dst)
        results.append(rec)
        print(f"[{'OK ' if rec.get('ok') else 'NG '}] {name}  {rec.get('reason', '')}", flush=True)

    with open(os.path.join(out, ".fetch-manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"manifest": args.manifest, "source": source, "out": out, "results": results},
                  fh, ensure_ascii=False, indent=1)
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n取回 {ok}/{len(results)}；落盘 {out}；失败项见 .fetch-manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

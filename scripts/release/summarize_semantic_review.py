#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT/"src") not in sys.path:sys.path.insert(0,str(ROOT/"src"))

from agent_worm_poc.review import summarize_completed_review  # noqa: E402


def _read_unique(path:Path)->tuple[list[str],dict[str,dict[str,str]]]:
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle);fields=list(reader.fieldnames or []);rows=list(reader)
    if "review_id" not in fields:raise ValueError(f"review_id is missing from {path}")
    by_id={}
    for row in rows:
        review_id=str(row.get("review_id") or "").strip()
        if not review_id or review_id in by_id:raise ValueError(f"missing or duplicate review_id in {path}")
        by_id[review_id]=row
    return fields,by_id


def merge_independent_reviews(packet:Path,reviewer_one:Path,reviewer_two:Path)->Path:
    fields,base=_read_unique(packet);_,first=_read_unique(reviewer_one);_,second=_read_unique(reviewer_two)
    if set(first)!=set(base) or set(second)!=set(base):
        raise ValueError("Reviewer files and the immutable packet have different review-ID sets")
    immutable=[field for field in fields if not field.startswith(("reviewer_","adjudicated_"))]
    for review_id,row in base.items():
        for candidate in (first[review_id],second[review_id]):
            if any(str(candidate.get(field) or "")!=str(row.get(field) or "") for field in immutable):
                raise ValueError(f"Reviewer file changed immutable packet content for {review_id}")
        for field in fields:
            if field.startswith("reviewer_1_"):row[field]=first[review_id].get(field,"")
            elif field.startswith("reviewer_2_"):row[field]=second[review_id].get(field,"")
    output=packet.with_name("semantic_review_completed.csv")
    with output.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(base.values())
    return output


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Merge and validate the blinded dual-review packet")
    parser.add_argument("packet",type=Path,help="Immutable semantic_review_blinded.csv")
    parser.add_argument("--reviewer-one",type=Path)
    parser.add_argument("--reviewer-two",type=Path)
    parser.add_argument("--output-dir",type=Path)
    args=parser.parse_args(argv)
    if bool(args.reviewer_one)!=bool(args.reviewer_two):
        parser.error("--reviewer-one and --reviewer-two are required together")
    completed=(merge_independent_reviews(args.packet,args.reviewer_one,args.reviewer_two)
               if args.reviewer_one else args.packet)
    summary=summarize_completed_review(completed,args.output_dir or args.packet.parent)
    print(json.dumps({"review_csv":str(completed),"summary":summary},indent=2))
    return 0


if __name__=="__main__":raise SystemExit(main())

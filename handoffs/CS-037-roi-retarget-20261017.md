# CS-037 manual ROI retarget regression

Branch: task/CS-037-signal-parser.
Implementation base: 54e1a454211826e96e2ec9519f35f155ed56fcaa.
Accepted main integration: 873fcb02e19c3a49531cc6cddf6c86340b01fd35.

Final review found that a translated manual box with the same target ID could
inherit confirmation. The added regression first failed: expected unknown, got
walk. Select by (target ID, exact box geometry), clearing prior evidence when
either changes. The regression then passed and needs two newly confirmed frames.

Changed own parser, test, usage notes, task evidence and new audit records/log.
Original handoff/fragment/report remain unchanged historical execution evidence.
After correction all 46 vision tests passed (15 parser) and the 18-frame replay
CLI still passed. Checked publishing reruns shared/structure/log/whitespace.
No live mode, model training, production adapter, real accuracy, transport or
hardware changes. Michael review/merge remains required.

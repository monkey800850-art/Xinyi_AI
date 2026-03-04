import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from app.services.report_result_tree import rows_to_tree

rows=[
 {"person":"A","subject":"6601","dept":"HR","amount":100},
 {"person":"A","subject":"6602","dept":"HR","amount":50}
]

tree=rows_to_tree(rows,["person","subject","dept"])

print("PASS tree build")
print(tree)

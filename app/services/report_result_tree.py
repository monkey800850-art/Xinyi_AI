"""
REPORTS-QUERY-04
Convert flat report rows into hierarchical tree according to group_by order.
"""

def rows_to_tree(rows, group_by, value_field="amount"):
    root = {}

    for r in rows:
        node = root
        for g in group_by:
            key = r.get(g)

            if key not in node:
                node[key] = {"_children": {}, "_value": 0}

            node[key]["_value"] += r.get(value_field,0)

            node = node[key]["_children"]

    return root

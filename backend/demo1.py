from treeMemoryStore import TreeMemoryStore

store = TreeMemoryStore("localnexus")
# 查询所有 Tech 类别的记忆（level=2 为具体记忆节点）
memories = store.query_memories(root_category="Tech", level=2)
print(f"找到 {len(memories)} 条 Tech 记忆：")
for mem in memories:
    print(f"- {mem['title']}: {mem['summary'][:50]}...")

input("按任意键继续...")
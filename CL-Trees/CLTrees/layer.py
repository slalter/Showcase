from CLTrees.node import Node
from CLTrees.timeRange import TimeRange

class Layer:
    def __init__(self):
        self.nodes = []

    def add_node(self, node: Node):
        self.nodes.append(node)
        self.nodes.sort(key=lambda x: x.time_range.minTime) 

    def get_node_by_time_range(self, target_time_range: TimeRange):
        left, right = 0, len(self.nodes) - 1

        while left <= right:
            mid = left + (right - left) // 2
            node = self.nodes[mid]

            if target_time_range.subset_of(node.time_range):
                return node
            elif node.time_range.minTime > target_time_range.minTime:
                right = mid - 1
            else:
                left = mid + 1

        return None
    
    def __str__(self):
        return f"{[str(node) for node in self.nodes]}"
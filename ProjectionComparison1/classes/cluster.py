class Element:
    '''
    represents an element in the cluster
    '''
    def __init__(self, name, embedding):
        self.name = name
        self.embedding = embedding

    def __str__(self):
        return f'{self.name}: ' + 'has embedding' if self.embedding else 'has no embedding'


class ClusterGroup:
    '''
    represents one individual grouping within a cluster
    '''
    def __init__(self, label, elements: list[Element]):
        self.label = label
        self.elements = elements

class Cluster:
    '''
    class to contain the cluster data objects like below:
        "goodness": {
        "0": [
            "quicksand",
            "plastic",
            "sack",
            "laugh",
            "treatment",
            "instrument",
            "ocean",
            "hand",
            "shock"
        ],
        "1": [
            "peace"
        ],
        "2": [
            "stream",
            "clam",
            "increase",
            "representative",
            "flight",
            "salt"
        ],
        "3": [
            "toy",
            "power"
        ],
        "4": [
            "air",
            "push"
        ]
    }
    '''
    def __init__(self, directive, sets: list[ClusterGroup]):
        self.directive = directive
        self.sets = sets

    def __str__(self):
        result = self.directive + '\n'
        for group in self.sets:
            result += f'{group.label}: {group.elements}\n'
        return result


class ClusterSet:
    '''
    holds a partition of clusters.
    '''
    def __init__(self, clusters: list[Cluster]):
        self.clusters = clusters
        self.num_clusters = len(clusters)

    def __str__(self):
        result = ''
        for cluster in self.clusters:
            result += cluster.__str__()
        return result

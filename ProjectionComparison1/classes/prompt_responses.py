class FindElementResponse:
    '''
    contains directive:description pairs
    '''
    pairs = list[tuple[str, str]]
    def __init__(self, pairs):
        self.pairs = pairs
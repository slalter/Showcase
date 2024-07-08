from classes import ClusterSet, Cluster, ClusterGroup, Element
from prompt_classes import FindElementPrompt
import numpy as np

def llmDescribeElement(cluster:ClusterSet, element):
    """
    Attempt to find the cluster that contains the given element.

    Parameters:
    clusters (dict): A dictionary where the keys are the directives of the clusters and the values are the elements themselves.
    element (str): The element to search for.
    """

    prompt=FindElementPrompt(
        directives = [cluster.directive for cluster in cluster.clusters],
        target_element = element
    )
    log, result = prompt.execute()
    cluster_summaries:list[tuple[Cluster, str]] = []
    for directive, summary in result.items():
        for c in cluster.clusters:
            if c.directive == directive:
                cluster_summaries.append((c, summary))
                break
    
    return cluster_summaries

def findElement(clusterset:ClusterSet, numElements = 1):
    '''
    Attempt to use an LLM to find the element in each cluster in the clusterset.
    numElements is how many we try to test for. Picks at random.
    '''
    all_elements = [s.elements for s in clusterset.clusters[0].sets]
    all_elements = [item for sublist in all_elements for item in sublist]
    to_find = np.random.choice(all_elements, numElements)
    element_cluster_summaries:list[tuple[Element, Cluster, str]] = []
    for element in to_find:
        cluster_summaries = llmDescribeElement(clusterset, element)
        for c, summary in cluster_summaries:
            element_cluster_summaries.append((element, c, summary))

    
        #for each response, embed the description and compare it to each set in each cluster.



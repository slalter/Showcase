from data_sets import manager
import dotenv
import numpy as np
import json
dotenv.load_dotenv('.env')
from operations.cluster import cluster_vectors
from operations.project import project_vector
from guru.GLLM import LLM
def naive():
    '''
    simple noun projection and clustering.
    '''
    dataset = manager.getSet('nouns1', embedded=True)
    sort_by = ['health', 'goodness','evil']
    dataset2 = [[string,np.array(LLM.getEmbedding(string))] for string in sort_by]
    num_nouns = 20
    num_clusters = 5

    #project the first n nouns in the dataset onto each noun in the second dataset
    projections = []
    clusters = {}
    
    for i in range(len(sort_by)):
        temp = []
        noun, embedding = dataset2[i]
        for noun2, embedding2 in dataset[:num_nouns]:
            projection = project_vector(embedding2, embedding)
            temp.append(projection)
        projections.append(temp)
    
        #cluster the projections
        labels, centroids = cluster_vectors(projections[i], num_clusters)
        #set up noun: [list of nouns in cluster] dictionary
        clusters[noun] = {}
        for label in range(num_clusters):
            clusters[noun][label] = []
        for j in range(len(labels)):
            clusters[noun][labels[j]].append(dataset[j][0])
        
    print(json.dumps(clusters, indent=4))

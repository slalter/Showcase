from data_sets import manager
import dotenv
import numpy as np
import json
dotenv.load_dotenv('.env')
from operations.cluster import cluster_vectors
from operations.project import project_vector, project_with_relative_output
from classes import ClusterSet, Cluster, ClusterGroup
from guru.GLLM import LLM
import guru.Flows

quality_pairs = [
['hoka','runner','Dakota','curling'],
['artist','paintbrush', 'writer','pen'], 
['teacher', 'chalkboard', 'chef', 'stove'],
    ['doctor', 'stethoscope', 'plumber', 'wrench'],
    ['singer', 'microphone', 'dancer', 'stage'],
    ['carpenter', 'hammer', 'gardener', 'shovel'],
    ['pilot', 'cockpit', 'sailor', 'deck'],
    ['photographer', 'camera', 'scientist', 'microscope'],
    ['firefighter', 'hose', 'police officer', 'handcuffs'],
    ['athlete', 'trophy', 'student', 'diploma'],
    ['musician', 'instrument', 'painter', 'canvas'],
    ['architect', 'blueprint', 'author', 'manuscript']
]

def main():
    dataset = manager.getSet('analogous2000',True)
    qps = quality_pairs
    for qp in qps:
        for i in range(len(qp)):
            qp[i] = [qp[i], np.array(LLM.getEmbedding(qp[i]))]
    N = 2000
    print("Sample data from dataset:")
    for i in range(5):
        print(dataset[np.random.randint(len(dataset))])
    
    datas = []
    for _ in range(N):
        s = [dataset[np.random.randint(len(dataset))] for _ in range(4)]
        while(any([s[i][0] == s[j][0] for i in range(4) for j in range(4) if i != j])):
            s = [dataset[np.random.randint(len(dataset))] for _ in range(4)]
        datas.append(s)
    for qp in qps:
        datas.append(qp) 
    for data in datas:
        a, b, x, y = data
        
        projection1 = project_with_relative_output(x[1], y[1], normalize=True)
        projection2 = project_with_relative_output(a[1], b[1], normalize=True)

        #lets just do elementwise subtraction
        #projection1 = x[1] - y[1]
        #projection2 = a[1] - b[1]

        #brainstorm: what other ways could we identify the aspects of each vectors which make them similar?
        
        #cosine similarity
        similarity = np.dot(projection1, projection2) / (np.linalg.norm(projection1) * np.linalg.norm(projection2))
 
        
        data.append(similarity)
    

    datas = sorted(datas, key=lambda x: x[4], reverse=True)
    
    print("Sorted dataset with similarity scores:")
    for d in datas[:10]:  # Print first 5 for brevity
        print((d[0][0], d[1][0], d[2][0], d[3][0], d[4]))

    #print the worst 5 as well
    print("Worst 5:")
    for d in datas[-10:]:
        print((d[0][0], d[1][0], d[2][0], d[3][0], d[4]))

    #find the location of the quality pairs in the sorted results. print the list of indexes, as well as total length.
    print("Quality pairs:")
    results = []
    for qp in qps:
        #find the index
        index = None
        for i, d in enumerate(datas):
            if d[0][0] == qp[0][0] and d[1][0] == qp[1][0] and d[2][0] == qp[2][0] and d[3][0] == qp[3][0]:
                index = i
                break
        results.append((index, [(qp[0][0], qp[1][0], qp[2][0], qp[3][0], index) for qp in qps]))
    for r in results:
        print(r)
    print(len(datas))
   
    #scatterplot the positions of the quality pairs in the sorted dataset.
    import matplotlib.pyplot as plt
    for r in results:
        plt.scatter(r[0], [0 for _ in range(len(r[0]))])
    plt.show()

if __name__ == '__main__':
    main()
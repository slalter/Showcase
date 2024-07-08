from sklearn.cluster import KMeans
import numpy as np

def cluster_vectors(vectors, n_clusters):
    """
    Cluster the given set of vectors using the K-means algorithm.

    Parameters:
    vectors (np.array): A 2D numpy array where each row is a vector.
    n_clusters (int): The number of clusters to form.

    Returns:
    tuple: A tuple containing:
        - labels (np.array): An array of integer labels indicating the cluster assignment of each vector.
        - centroids (np.array): A 2D array where each row is the centroid of a cluster.
    """
    # Create a KMeans instance with the specified number of clusters
    kmeans = KMeans(n_clusters=n_clusters)
    
    # Fit the model to the data and predict the cluster labels
    labels = kmeans.fit_predict(vectors)
    
    # Extract the centroids
    centroids = kmeans.cluster_centers_
    
    return labels, centroids
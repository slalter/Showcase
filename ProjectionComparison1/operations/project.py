from guru.GLLM import LLM
import numpy as np
def project_vector(v, u):
    """
    Project vector v onto vector u in 1536-dimensional space.

    Parameters:
    v (np.array): A numpy array representing the vector to be projected.
    u (np.array): A numpy array representing the vector to project onto.

    Returns:
    np.array: The projection of v onto u.
    """
    # Calculate the dot product of v and u
    dot_product = np.dot(v, u)
    
    # Calculate the norm squared of u
    norm_u_squared = np.dot(u, u)
    
    # Calculate the projection
    projection = (dot_product / norm_u_squared) * u
    return projection

def project_with_relative_output(v, u, normalize = True):
    '''
    take into account the dimensions of the vectors which are contributing to the final magnitude of the projection.
    Returns an array of the same length as the input vectors, where each element is the relative impact of the corresponding dimension on the projection's overall magnitude.
    output is normalized to sum to 1.
    '''
    projection = project_vector(v, u)
    projection_magnitude = np.linalg.norm(projection)
    #for each dimension, calculate the relative impact on the projection's magnitude
    relative_output = []
    for i in range(len(v)):
        contribution = v[i] - u[i]
        relative_output.append(contribution / projection_magnitude)

    #normalize the output
    if normalize:
        relative_output = np.array(relative_output)
        relative_output = relative_output / np.sum(relative_output)
    return relative_output
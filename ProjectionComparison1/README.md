This is a set of NLP experiments to assess if I can use existing embedding models to create and compare relative embeddings by projecting vectors and other methods.

For example:

apples are to red -> embedding1
the sky is to blue -> embedding2

cosine_similarity(embedding1, embedding2)

So we can (pseudocode):

apples are to red -> embedding
embeddings = []
for i, item in enumerate(item_list):
    embeddings[i] = item is to red -> embedding

and use that to find other red items in the list. 

Abstracting this further could be quite useful for RAG and other NLP applications. 

Findings were that we likely need to train our own embedding model on relationships.
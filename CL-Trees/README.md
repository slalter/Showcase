This project from my time at NewSeat was an abstraction of my 'L-Trees' (see L-Trees) to Chronological L-Trees.

The bottom layer of the tree is individual tasks that are completed in chronological order.

They are up-summarized in groups based on how semantically similar they are to their neighbors. During conversation, an (old and clunky) LLM system dynamically determines how deep to go down each branch of the tree to curate the appropriate context for the current task.

Both types of trees have since been abstracted to DynamicContextObjects (see TechGuru)
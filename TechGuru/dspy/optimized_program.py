{
  "seed_predictor.predictor": {
    "lm": null,
    "traces": [],
    "train": [],
    "demos": [],
    "signature_instructions": "As an expert code generator, create a list of 3-4 word example seeds that can be used to generate diverse, concise code snippets across various programming languages and paradigms. Each seed should be unique and suggestive of a specific coding concept, algorithm, or programming technique. Aim for a mix of difficulty levels and applicability to different domains of software development.",
    "signature_prefix": "Example seeds:\n\n1."
  },
  "code_predictor": {
    "lm": null,
    "traces": [],
    "train": [],
    "demos": [],
    "signature_instructions": "As a Python code generator specializing in type-related issues, your task is to create a concise code snippet that would trigger a pyright error due to insufficient typing information. The code should be syntactically correct but lack proper type annotations, causing pyright to raise concerns. Focus on common scenarios where type hints are crucial for static type checking. Provide only the code snippet without any explanations or comments. Do NOT restate the seed.",
    "signature_prefix": "Code:"
  }
}
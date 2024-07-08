from datetime import timedelta
from datetime import datetime
# Starting date for the project
start_date = datetime(2023, 9, 1, 9, 0)

# Function to generate timestamps for each step with an interval of 3 days
def generate_timestamps(start_date, num_steps, interval_days=3):
    return [start_date + timedelta(days=i*interval_days) for i in range(num_steps)]

# Generating timestamps for 50 steps
timestamps = generate_timestamps(start_date, 50)

# Granular steps in software development process
granular_steps = [
    "Project charter creation", "Stakeholder identification", "Initial risk assessment",
    "Resource allocation", "Project kickoff meeting", "Stakeholder interviews",
    "User requirement workshops", "Creation of user stories", "Requirement documentation",
    "Requirement sign-off", "Feasibility study", "Data flow diagrams", "System models",
    "Requirements validation", "Architecture design", "User interface design", 
    "Database design", "Security design", "Algorithm design", "Setup development environment",
    "Code the functionality", "Database setup", "Unit testing", "Code review",
    "Writing test cases", "Functional testing", "Integration testing", "Performance testing",
    "Security testing", "Preparing deployment environment", "Data migration", "System deployment",
    "User training", "Go-live", "User feedback collection", "Bug fixing", "Performance tuning",
    "Feature updates", "Regular system audits", "Regular team meetings", "Progress tracking",
    "Risk management", "Stakeholder communication", "Documentation", "Code quality checks",
    "Design review", "Process compliance audit", "User acceptance testing", "Release sign-off",
    "Final project documentation", "Project closure report", "Post-implementation review",
    "Stakeholder debriefing", "Resource reallocation"
]

# Pairing each step with its corresponding timestamp
detailed_software_development_timeline = list(zip(granular_steps, timestamps))

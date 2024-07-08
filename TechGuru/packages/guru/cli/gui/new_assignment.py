import tkinter as tk
from tkinter import simpledialog, messagebox
import inspect

assignment_data_holder = {"data": None}  
def create_or_edit_assignment(input_json=None):
    from packages.guru.Flows.features import feature_classes 
    from packages.guru.Flows.tool import available_tools 
    root = tk.Tk()
    root.title("Create/Edit Assignment")
    root.geometry("3000x2000")  # Adjusted for additional fields

    # Initialize variables for new features
    connectors = []
    check_complete_after_tools_var = tk.BooleanVar(value=False)
    message_after_complete_var = tk.BooleanVar(value=False)
    feature_vars = {}
    feature_inputs = {}

    # Function to dynamically create input fields for feature parameters
    def toggle_feature(feature_class, var, frame, row):
        if var.get():
            params = inspect.signature(feature_class.__init__).parameters
            param_row = row + 1
            for param in list(params)[2:]:  # Adjusted to skip 'self' and 'assignment'
                label = tk.Label(frame, text=f"{param}:")
                label.grid(row=param_row, column=0, padx=5, pady=3, sticky='w')
                entry = tk.Text(frame, width=50, height=2)  # Adjust size as needed
                entry.grid(row=param_row, column=1, padx=5, pady=3, sticky='ew')
                feature_inputs[feature_class.__name__][param] = entry
                param_row += 1
            frame.grid(row=row, column=1, columnspan=2, sticky='ew', padx=10, pady=5)
        else:
            for widget in frame.winfo_children():
                widget.destroy()
            frame.grid_forget()

    # Assignment details fields
    id_label = tk.Label(root, text="Assignment ID:")
    id_label.grid(row=0, column=0, padx=10, pady=10, sticky='w')
    id_entry = tk.Entry(root)
    id_entry.grid(row=0, column=1, padx=10, pady=10, sticky='ew')

    guidelines_label = tk.Label(root, text="Guidelines:")
    guidelines_label.grid(row=1, column=0, padx=10, pady=10, sticky='w')
    guidelines_entry = tk.Text(root, width=100, height=10)  # Adjusted width and height
    guidelines_entry.grid(row=1, column=1, padx=10, pady=10, sticky='ew')

    objectives_label = tk.Label(root, text="Objectives:")
    objectives_label.grid(row=2, column=0, padx=10, pady=10, sticky='w')
    objectives_entry = tk.Text(root, width=100, height=10)  # Adjusted width and height
    objectives_entry.grid(row=2, column=1, padx=10, pady=10, sticky='ew')

    # Features selection and dynamic input fields
    features_label = tk.Label(root, text="Select Features:")
    features_label.grid(row=3, column=0, padx=10, pady=10, sticky='w')
    for idx, cls in enumerate(feature_classes):
        feature_frame = tk.Frame(root)
        var = tk.BooleanVar()
        chk = tk.Checkbutton(root, text=cls.__name__, variable=var)
        chk.grid(row=4+idx, column=0, padx=10, pady=2, sticky='w')
        var.trace_add('write', lambda name, index, mode, cls=cls, var=var, frame=feature_frame, row=4+idx: toggle_feature(cls, var, frame, row))
        feature_vars[cls.__name__] = var
        feature_inputs[cls.__name__] = {}

    # Checkboxes for "Check Complete After Tools" and "Message After Complete"
    check_complete_checkbox = tk.Checkbutton(root, text="Check Complete After Tools", variable=check_complete_after_tools_var)
    check_complete_checkbox.grid(row=105, column=0, padx=10, pady=5, sticky='w')

    message_after_complete_checkbox = tk.Checkbutton(root, text="Message After Complete", variable=message_after_complete_var)
    message_after_complete_checkbox.grid(row=106, column=0, padx=10, pady=5, sticky='w')

    # Function to add a new connector
    def add_connector(connector_data=None):
        connector_frame = tk.Frame(root)
        next_row = len(connectors) + 107  # Adjust based on actual layout
        connector_frame.grid(row=next_row, column=0, columnspan=2, padx=10, pady=5, sticky='ew')

        target_assignment_label = tk.Label(connector_frame, text="Target Assignment:")
        target_assignment_label.grid(row=0, column=0, padx=5, pady=3)
        target_assignment_entry = tk.Entry(connector_frame)
        target_assignment_entry.grid(row=0, column=1, padx=5, pady=3)
        if connector_data:  # Prepopulate if data is provided
            target_assignment_entry.insert(0, connector_data.get("targetAssignment", ""))

        criteria_label = tk.Label(connector_frame, text="Criteria:")
        criteria_label.grid(row=1, column=0, padx=5, pady=3)
        criteria_entry = tk.Entry(connector_frame)
        criteria_entry.grid(row=1, column=1, padx=5, pady=3)
        if connector_data:  # Prepopulate if data is provided
            criteria_entry.insert(0, connector_data.get("criteria", ""))

        reprompt_label = tk.Label(connector_frame, text="Reprompt:")
        reprompt_label.grid(row=2, column=0, padx=5, pady=3)
        reprompt_entry = tk.Entry(connector_frame)
        reprompt_entry.grid(row=2, column=1, padx=5, pady=3)
        if connector_data:  # Prepopulate if data is provided
            reprompt_entry.insert(0, connector_data.get("reprompt", ""))

        connectors.append({
            "frame": connector_frame,
            "target_assignment_entry": target_assignment_entry,
            "criteria_entry": criteria_entry,
            "reprompt_entry": reprompt_entry
        })

    add_connector_btn = tk.Button(root, text="Add Connector", command=lambda: add_connector())
    add_connector_btn.grid(row=107, column=0, padx=10, pady=10)

    # Tools selection and dynamic input fields
    tools_label = tk.Label(root, text="Select Tools:")
    tools_label.grid(row=109, column=0, padx=10, pady=10, sticky='w')  # Adjust row as necessary
    tools_vars = {}



    for idx, tool in enumerate(available_tools):
        tool_frame = tk.Frame(root)
        var = tk.BooleanVar()
        chk = tk.Checkbutton(root, text=tool["function"]["name"], variable=var)
        chk.grid(row=110+idx, column=0, padx=10, pady=2, sticky='w')  # Adjust row as necessary
        tools_vars[tool["function"]["name"]] = var

    def on_submit():
        # Collect data from the UI
        assignment_id = id_entry.get()
        guidelines_text = guidelines_entry.get("1.0", tk.END).strip()
        objectives_text = objectives_entry.get("1.0", tk.END).strip()
        
        # Process guidelines and objectives text into lists if they are separated by new lines
        guidelines = guidelines_text.split("\n") if guidelines_text else []
        objectives = objectives_text.split("\n") if objectives_text else []
        
        # Collect features data
        features_data = []
        for feature_name, inputs in feature_inputs.items():
            if feature_vars[feature_name].get():  # If the feature is selected
                feature_args = {}
                for param, entry in inputs.items():
                    param_value = entry.get("1.0", tk.END).strip()  # Assuming these are Text widgets
                    feature_args[param] = param_value
                features_data.append({"featureName": feature_name, "args": feature_args})

        # Collect connectors data
        connectors_data = []
        for connector in connectors:
            connector_data = {
                "targetAssignment": connector["target_assignment_entry"].get(),
                "criteria": connector["criteria_entry"].get(),
                "reprompt": connector["reprompt_entry"].get(),
            }
            connectors_data.append(connector_data)
        

        tools_data = []
        for tool_name, result in tools_vars.items():
            if tools_vars[tool_name].get():
                tools_data.append([tool_name])

        # Assemble the assignment data into a dictionary
        assignment_data = {
            "id": assignment_id,
            "guidelines": guidelines,
            "objectives": objectives,
            "features": features_data,
            "connectors": connectors_data,
            "check_complete_after_tools": check_complete_after_tools_var.get(),
            "message_after_complete": message_after_complete_var.get(),
            "tools":tools_data
        }

        global assignment_data_holder
        assignment_data_holder['data'] = assignment_data


        root.destroy()  # Close the window after submission

        return assignment_data_holder['data']

     # Assign on_submit to your submit button
    submit_btn = tk.Button(root, text="Submit", command=on_submit)
    submit_btn.grid(row=108, column=0, columnspan=2, padx=10, pady=10)

    # Function to prepopulate fields from JSON, if provided
    def populate_fields_from_json():
        if input_json:
            id_entry.insert(0, input_json.get("id", ""))
            guidelines_entry.insert("1.0", "\n".join(input_json.get("guidelines", [])))
            objectives_entry.insert("1.0", "\n".join(input_json.get("objectives", [])))
            check_complete_after_tools_var.set(input_json.get("check_complete_after_tools", False))
            message_after_complete_var.set(input_json.get("message_after_complete", False))
            # More logic to populate connectors and features if necessary

    populate_fields_from_json()

    root.mainloop()

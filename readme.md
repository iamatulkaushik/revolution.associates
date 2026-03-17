
# Project Details
project_name = "My Project"
project_version = "1.0.0"
project_description = "A sample project for demonstration purposes"
project_author = "Developer Name"
project_license = "MIT"
project_created_date = "2024-01-01"
project_status = "Active"

# Project configuration
project_details = {
    "name": project_name,
    "version": project_version,
    "description": project_description,
    "author": project_author,
    "license": project_license,
    "created_date": project_created_date,
    "status": project_status,
    "dependencies": [],
    "repository": "",
    "homepage": ""
}

def get_project_details():
    """Returns the project details dictionary"""
    return project_details

def update_project_detail(key, value):
    """Updates a specific project detail"""
    if key in project_details:
        project_details[key] = value
        return True
    return False

def display_project_info():
    """Displays formatted project information"""
    print(f"Project: {project_details['name']}")
    print(f"Version: {project_details['version']}")
    print(f"Description: {project_details['description']}")
    print(f"Author: {project_details['author']}")
    print(f"License: {project_details['license']}")
    print(f"Status: {project_details['status']}")
    print(f"Created Date: {project_details['created_date']}")

# Example usage
display_project_info()
update_project_detail("status", "Inactive")
display_project_info()
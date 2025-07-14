"""This script is used to sanitize the file name."""
import re

def up(name):
    """
    Sanitize the file name by replacing spaces with hyphens,
    removing non-alphanumeric characters except dots and hyphens,
    converting to lowercase for the main part of the filename,
    while preserving the original case and hyphens inside square brackets.
    """
    # Pattern to identify text within square brackets
    bracket_pattern = re.compile(r'\[([^\]]+)\]')

    # Function to sanitize the main part of the filename
    def alphanumeric(text):
        sanitization = text.replace(' ', '-')
        sanitization = re.sub(r'[^a-zA-Z0-9.\-_]', '', sanitization)
        sanitization = re.sub(r'-{2,}', '-', sanitization)
        sanitization = sanitization.lower()
        sanitization = sanitization.strip('-')
        return sanitization

    # Function to sanitize the text inside brackets without changing case or collapsing hyphens
    def hashid(text):
        sanitization = re.sub(r'[^a-zA-Z0-9.\-_]', '', text)
        return sanitization

    # Split the filename into parts outside and inside brackets
    parts = bracket_pattern.split(name)
    sanitized_parts = [
        f'-[{hashid(part)}]' if index % 2 == 1
        else alphanumeric(part)
        for index, part in enumerate(parts)
    ]

    # Reassemble the sanitized filename
    sanitized_name = ''.join(sanitized_parts)
    return sanitized_name

import os
import re

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

replacements = {
    r"url_for\('login'\)": "url_for('auth.login')",
    r'url_for\("login"\)': "url_for('auth.login')",
    r"url_for\('register'\)": "url_for('auth.register')",
    r'url_for\("register"\)': "url_for('auth.register')",
    r"url_for\('logout'\)": "url_for('auth.logout')",
    r'url_for\("logout"\)': "url_for('auth.logout')",
    r"url_for\('profile'\)": "url_for('profile')", # we kept profile in app.py
}

for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = re.sub(old, new, new_content)
                
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Updated {file}")

# Also let's completely rip out the old auth routes from app.py
app_py_path = os.path.join(os.path.dirname(__file__), 'app.py')
with open(app_py_path, 'r', encoding='utf-8') as f:
    app_lines = f.readlines()

new_app_lines = []
skip = False
for line in app_lines:
    if line.startswith('@app.route(\'/register\''):
        skip = True
    elif line.startswith('@app.route(\'/login\''):
        skip = True
    elif line.startswith('@app.route(\'/logout\''):
        skip = True
        
    if skip and line.startswith('# ── Profile'):
        skip = False
        
    if not skip:
        new_app_lines.append(line)

with open(app_py_path, 'w', encoding='utf-8') as f:
    f.writelines(new_app_lines)
print("Updated app.py")

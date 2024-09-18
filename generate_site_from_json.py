import json
import shutil

from jinja2 import Environment, FileSystemLoader

if __name__ == "__main__":
    # Load current config
    with open('docs/apps.json') as app_data:
        apps = json.load(app_data)
    
    # Copy CSS
    shutil.copy('static/style.css', 'docs')
    
    # Render template
    template = Environment(loader=FileSystemLoader('templates')).get_template('index.html.j2')
    with open('docs/index.html', 'w+') as f:
        html = template.render(apps=apps)
        f.write(html)

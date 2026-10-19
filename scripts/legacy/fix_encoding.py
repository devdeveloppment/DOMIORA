import os

files = [
    'templates/base.html',
    'templates/dashboard/dashboard_base.html',
    'templates/partials/footer.html',
    'templates/properties/detail.html',
    'templates/dashboard/admin/finances.html',
    'templates/dashboard/admin/properties.html',
    'templates/dashboard/admin/transactions.html'
]

for f in files:
    try:
        # Try to read as utf-8 first
        with open(f, 'r', encoding='utf-8') as file:
            content = file.read()
    except UnicodeDecodeError:
        try:
            # If not utf-8, maybe ANSI
            with open(f, 'r', encoding='mbcs') as file:
                content = file.read()
        except:
            # Or UTF-16
            with open(f, 'r', encoding='utf-16') as file:
                content = file.read()
    
    # Save as utf-8
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

print("Encoding fixed!")

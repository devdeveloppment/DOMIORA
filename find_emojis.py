import os, re

emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]', flags=re.UNICODE)

for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = emoji_pattern.findall(content)
                if matches:
                    print(f'{filepath}: {" ".join(set(matches))}')

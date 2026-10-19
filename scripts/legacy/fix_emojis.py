import os
import re

emoji_to_fa = {
    '📍': '<i class="fa-solid fa-location-dot"></i>',
    '👤': '<i class="fa-solid fa-user"></i>',
    '💬': '<i class="fa-solid fa-comment"></i>',
    '🎉': '<i class="fa-solid fa-champagne-glasses"></i>',
    '🛁': '<i class="fa-solid fa-bath"></i>',
    '📐': '<i class="fa-solid fa-ruler-combined"></i>',
    '🏠': '<i class="fa-solid fa-house"></i>',
    '🔍': '<i class="fa-solid fa-magnifying-glass"></i>',
    '📅': '<i class="fa-regular fa-calendar"></i>',
    '🤖': '<i class="fa-solid fa-robot"></i>',
    '🎬': '<i class="fa-solid fa-clapperboard"></i>',
    '📨': '<i class="fa-solid fa-envelope"></i>',
    '💰': '<i class="fa-solid fa-coins"></i>',
    '🔔': '<i class="fa-solid fa-bell"></i>',
    '✅': '<i class="fa-solid fa-check"></i>',
    '❌': '<i class="fa-solid fa-xmark"></i>',
    '🤝': '<i class="fa-solid fa-handshake"></i>',
    '🔓': '<i class="fa-solid fa-lock-open"></i>',
    '📬': '<i class="fa-solid fa-envelope-open"></i>',
    '📞': '<i class="fa-solid fa-phone"></i>',
    '🏢': '<i class="fa-solid fa-building"></i>',
    '⭐': '<i class="fa-solid fa-star"></i>',
    '🟢': '<i class="fa-solid fa-circle" style="color: #10b981;"></i>',
    'ℹ️': '<i class="fa-solid fa-circle-info"></i>',
    '👋': '<i class="fa-solid fa-hand"></i>',
    '🌟': '<i class="fa-solid fa-star text-yellow-400"></i>',
    '🏆': '<i class="fa-solid fa-trophy text-yellow-500"></i>',
    '🛡️': '<i class="fa-solid fa-shield-halved"></i>',
}

def replace_emojis():
    for root, dirs, files in os.walk('templates'):
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                for emoji, fa in emoji_to_fa.items():
                    new_content = new_content.replace(emoji, fa)
                
                # Remove remaining emojis (Emoji Presentation blocks)
                # We'll just remove character codes commonly associated with emojis
                emoji_pattern = re.compile(r'[\U00010000-\U0010ffff]')
                missing_emojis = emoji_pattern.findall(new_content)
                if missing_emojis:
                    print(f"Warning: Found unmapped emojis in {path}: {set(missing_emojis)}")
                
                new_content = emoji_pattern.sub('', new_content)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated {path}")
                    
if __name__ == '__main__':
    replace_emojis()

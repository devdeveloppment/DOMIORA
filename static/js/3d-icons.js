// DOMIORA 3D Real Estate Icons
class Icons3D {
  constructor() {
    this.init();
  }

  init() {
    this.create3DIcons();
    this.animateIcons();
  }

  create3DIcons() {
    // Find all icon containers
    const iconContainers = document.querySelectorAll('[data-3d-icon]');
    
    iconContainers.forEach(container => {
      const iconType = container.getAttribute('data-3d-icon');
      this.createIcon(container, iconType);
    });
  }

  createIcon(container, type) {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    
    camera.position.set(0, 0, 5);
    
    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0x71212d, 0.8);
    directionalLight.position.set(5, 5, 5);
    scene.add(directionalLight);
    
    // Create icon based on type
    const icon = this.createIconGeometry(type);
    scene.add(icon);
    
    // Animation
    const animate = () => {
      requestAnimationFrame(animate);
      icon.rotation.y += 0.01;
      icon.rotation.x = Math.sin(Date.now() * 0.001) * 0.1;
      renderer.render(scene, camera);
    };
    
    animate();
    
    // Mouse interaction
    container.addEventListener('mousemove', (e) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      
      icon.rotation.y = x * 0.5;
      icon.rotation.x = -y * 0.5;
    });
  }

  createIconGeometry(type) {
    const group = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({ 
      color: 0x71212d,
      roughness: 0.3,
      metalness: 0.7
    });
    
    switch(type) {
      case 'house':
        this.createHouseIcon(group, material);
        break;
      case 'building':
        this.createBuildingIcon(group, material);
        break;
      case 'key':
        this.createKeyIcon(group, material);
        break;
      case 'location':
        this.createLocationIcon(group, material);
        break;
      case 'bed':
        this.createBedIcon(group, material);
        break;
      case 'bath':
        this.createBathIcon(group, material);
        break;
      case 'car':
        this.createCarIcon(group, material);
        break;
      case 'tree':
        this.createTreeIcon(group, material);
        break;
      default:
        this.createDefaultIcon(group, material);
    }
    
    return group;
  }

  createHouseIcon(group, material) {
    // Base
    const baseGeometry = new THREE.BoxGeometry(2, 1.5, 2);
    const base = new THREE.Mesh(baseGeometry, material);
    base.position.y = -0.25;
    group.add(base);
    
    // Roof
    const roofGeometry = new THREE.ConeGeometry(1.5, 1, 4);
    const roofMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xd4af37,
      roughness: 0.3,
      metalness: 0.7
    });
    const roof = new THREE.Mesh(roofGeometry, roofMaterial);
    roof.position.y = 1;
    roof.rotation.y = Math.PI / 4;
    group.add(roof);
    
    // Door
    const doorGeometry = new THREE.BoxGeometry(0.5, 0.8, 0.1);
    const doorMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x8b4513,
      roughness: 0.7
    });
    const door = new THREE.Mesh(doorGeometry, doorMaterial);
    door.position.set(0, -0.25, 1.05);
    group.add(door);
  }

  createBuildingIcon(group, material) {
    // Main building
    const buildingGeometry = new THREE.BoxGeometry(1.5, 3, 1.5);
    const building = new THREE.Mesh(buildingGeometry, material);
    group.add(building);
    
    // Windows
    const windowGeometry = new THREE.BoxGeometry(0.3, 0.3, 0.1);
    const windowMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x87ceeb,
      emissive: 0x87ceeb,
      emissiveIntensity: 0.3
    });
    
    for (let i = -1; i <= 1; i += 2) {
      for (let j = -1; j <= 1; j += 1) {
        const window = new THREE.Mesh(windowGeometry, windowMaterial);
        window.position.set(i * 0.4, j * 0.8, 0.8);
        group.add(window);
      }
    }
  }

  createKeyIcon(group, material) {
    // Key head
    const headGeometry = new THREE.TorusGeometry(0.5, 0.15, 16, 32);
    const head = new THREE.Mesh(headGeometry, material);
    head.position.set(-0.5, 0, 0);
    group.add(head);
    
    // Key shaft
    const shaftGeometry = new THREE.BoxGeometry(1.5, 0.2, 0.1);
    const shaft = new THREE.Mesh(shaftGeometry, material);
    shaft.position.set(0.3, 0, 0);
    group.add(shaft);
    
    // Key teeth
    const toothGeometry = new THREE.BoxGeometry(0.1, 0.3, 0.1);
    for (let i = 0; i < 3; i++) {
      const tooth = new THREE.Mesh(toothGeometry, material);
      tooth.position.set(0.6 + i * 0.2, -0.2, 0);
      group.add(tooth);
    }
  }

  createLocationIcon(group, material) {
    // Pin body
    const bodyGeometry = new THREE.ConeGeometry(0.5, 1.5, 32);
    const body = new THREE.Mesh(bodyGeometry, material);
    body.rotation.x = Math.PI;
    body.position.y = 0.5;
    group.add(body);
    
    // Pin head
    const headGeometry = new THREE.SphereGeometry(0.4, 32, 32);
    const headMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xd4af37,
      roughness: 0.3,
      metalness: 0.7
    });
    const head = new THREE.Mesh(headGeometry, headMaterial);
    head.position.y = 1.2;
    group.add(head);
    
    // Center dot
    const dotGeometry = new THREE.CircleGeometry(0.15, 32);
    const dotMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffffff
    });
    const dot = new THREE.Mesh(dotGeometry, dotMaterial);
    dot.position.y = 1.2;
    dot.position.z = 0.35;
    group.add(dot);
  }

  createBedIcon(group, material) {
    // Bed frame
    const frameGeometry = new THREE.BoxGeometry(2, 0.3, 1.5);
    const frame = new THREE.Mesh(frameGeometry, material);
    frame.position.y = 0.15;
    group.add(frame);
    
    // Mattress
    const mattressGeometry = new THREE.BoxGeometry(1.8, 0.4, 1.3);
    const mattressMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.8
    });
    const mattress = new THREE.Mesh(mattressGeometry, mattressMaterial);
    mattress.position.y = 0.5;
    group.add(mattress);
    
    // Pillow
    const pillowGeometry = new THREE.BoxGeometry(0.8, 0.2, 0.4);
    const pillowMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xe0e0e0,
      roughness: 0.9
    });
    const pillow = new THREE.Mesh(pillowGeometry, pillowMaterial);
    pillow.position.set(-0.4, 0.8, -0.3);
    group.add(pillow);
  }

  createBathIcon(group, material) {
    // Tub
    const tubGeometry = new THREE.BoxGeometry(1.5, 0.5, 0.8);
    const tub = new THREE.Mesh(tubGeometry, material);
    tub.position.y = 0.25;
    group.add(tub);
    
    // Faucet
    const faucetGeometry = new THREE.CylinderGeometry(0.05, 0.05, 0.5, 16);
    const faucet = new THREE.Mesh(faucetGeometry, material);
    faucet.position.set(0, 0.7, 0.4);
    faucet.rotation.x = Math.PI / 4;
    group.add(faucet);
  }

  createCarIcon(group, material) {
    // Car body
    const bodyGeometry = new THREE.BoxGeometry(2, 0.5, 1);
    const body = new THREE.Mesh(bodyGeometry, material);
    body.position.y = 0.5;
    group.add(body);
    
    // Car top
    const topGeometry = new THREE.BoxGeometry(1, 0.4, 0.8);
    const top = new THREE.Mesh(topGeometry, material);
    top.position.set(-0.2, 0.9, 0);
    group.add(top);
    
    // Wheels
    const wheelGeometry = new THREE.CylinderGeometry(0.2, 0.2, 0.1, 16);
    const wheelMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x333333,
      roughness: 0.8
    });
    
    const wheelPositions = [
      [-0.6, 0.2, 0.5],
      [0.6, 0.2, 0.5],
      [-0.6, 0.2, -0.5],
      [0.6, 0.2, -0.5]
    ];
    
    wheelPositions.forEach(pos => {
      const wheel = new THREE.Mesh(wheelGeometry, wheelMaterial);
      wheel.position.set(...pos);
      wheel.rotation.x = Math.PI / 2;
      group.add(wheel);
    });
  }

  createTreeIcon(group, material) {
    // Trunk
    const trunkGeometry = new THREE.CylinderGeometry(0.15, 0.2, 1, 8);
    const trunkMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x8b4513,
      roughness: 0.9
    });
    const trunk = new THREE.Mesh(trunkGeometry, trunkMaterial);
    trunk.position.y = 0;
    group.add(trunk);
    
    // Foliage
    const foliageGeometry = new THREE.ConeGeometry(0.6, 1.5, 8);
    const foliageMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x228b22,
      roughness: 0.8
    });
    const foliage = new THREE.Mesh(foliageGeometry, foliageMaterial);
    foliage.position.y = 1.2;
    group.add(foliage);
  }

  createDefaultIcon(group, material) {
    // Cube as default
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const cube = new THREE.Mesh(geometry, material);
    group.add(cube);
  }

  animateIcons() {
    // Add hover effects to all 3D icons
    const iconContainers = document.querySelectorAll('[data-3d-icon]');
    
    iconContainers.forEach(container => {
      container.addEventListener('mouseenter', () => {
        gsap.to(container, {
          scale: 1.1,
          duration: 0.3,
          ease: 'power2.out'
        });
      });
      
      container.addEventListener('mouseleave', () => {
        gsap.to(container, {
          scale: 1,
          duration: 0.3,
          ease: 'power2.out'
        });
      });
    });
  }
}

// Initialize 3D icons
document.addEventListener('DOMContentLoaded', () => {
  new Icons3D();
});

// Add 3D icon attributes to existing icons
function add3DIconAttributes() {
  const iconSelectors = {
    'house': '[class*="home"], [class*="house"], svg[class*="home"]',
    'building': '[class*="building"], svg[class*="building"]',
    'key': '[class*="key"], svg[class*="key"]',
    'location': '[class*="location"], [class*="map"], svg[class*="location"]',
    'bed': '[class*="bed"], svg[class*="bed"]',
    'bath': '[class*="bath"], svg[class*="bath"]',
    'car': '[class*="car"], svg[class*="car"]',
    'tree': '[class*="tree"], svg[class*="tree"]'
  };
  
  Object.entries(iconSelectors).forEach(([type, selector]) => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
      if (!element.hasAttribute('data-3d-icon')) {
        element.setAttribute('data-3d-icon', type);
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', add3DIconAttributes);

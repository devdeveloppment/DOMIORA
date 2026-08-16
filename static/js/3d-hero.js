// DOMIORA 3D Hero Section - Premium Villa Animation
class Hero3D {
  constructor() {
    this.container = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.villa = null;
    this.particles = null;
    this.mouseX = 0;
    this.mouseY = 0;
    this.targetRotationX = 0;
    this.targetRotationY = 0;
    this.init();
  }

  init() {
    // Find hero container
    this.container = document.querySelector('#hero-3d-container');
    if (!this.container) return;

    // Scene setup
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x0b3b5c, 10, 50);

    // Camera setup
    this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.camera.position.set(0, 5, 15);
    this.camera.lookAt(0, 2, 0);

    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    // Lighting
    this.setupLighting();

    // Create villa
    this.createVilla();

    // Create particles
    this.createParticles();

    // Event listeners
    this.addEventListeners();

    // Start animation
    this.animate();
  }

  setupLighting() {
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambientLight);

    // Main directional light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 20, 10);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    this.scene.add(directionalLight);

    // Fill light
    const fillLight = new THREE.DirectionalLight(0x71212d, 0.3);
    fillLight.position.set(-10, 10, -10);
    this.scene.add(fillLight);

    // Rim light
    const rimLight = new THREE.DirectionalLight(0x0b3b5c, 0.5);
    rimLight.position.set(0, 5, -15);
    this.scene.add(rimLight);
  }

  createVilla() {
    this.villa = new THREE.Group();

    // Main building
    const mainGeometry = new THREE.BoxGeometry(8, 4, 6);
    const mainMaterial = new THREE.MeshStandardMaterial({ 
      color: 0xf5f5f5,
      roughness: 0.8,
      metalness: 0.1
    });
    const mainBuilding = new THREE.Mesh(mainGeometry, mainMaterial);
    mainBuilding.position.y = 2;
    mainBuilding.castShadow = true;
    mainBuilding.receiveShadow = true;
    this.villa.add(mainBuilding);

    // Roof
    const roofGeometry = new THREE.ConeGeometry(6, 3, 4);
    const roofMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x71212d,
      roughness: 0.6,
      metalness: 0.2
    });
    const roof = new THREE.Mesh(roofGeometry, roofMaterial);
    roof.position.y = 5.5;
    roof.rotation.y = Math.PI / 4;
    roof.castShadow = true;
    this.villa.add(roof);

    // Windows
    const windowGeometry = new THREE.BoxGeometry(1.5, 1.5, 0.1);
    const windowMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x87ceeb,
      roughness: 0.1,
      metalness: 0.8,
      transparent: true,
      opacity: 0.7
    });

    for (let i = -2; i <= 2; i += 2) {
      const window = new THREE.Mesh(windowGeometry, windowMaterial);
      window.position.set(i, 2.5, 3.05);
      this.villa.add(window);
    }

    // Door
    const doorGeometry = new THREE.BoxGeometry(2, 3, 0.1);
    const doorMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x8b4513,
      roughness: 0.7,
      metalness: 0.1
    });
    const door = new THREE.Mesh(doorGeometry, doorMaterial);
    door.position.set(0, 1.5, 3.05);
    this.villa.add(door);

    // Ground
    const groundGeometry = new THREE.PlaneGeometry(30, 30);
    const groundMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x90a955,
      roughness: 1,
      metalness: 0
    });
    const ground = new THREE.Mesh(groundGeometry, groundMaterial);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0;
    ground.receiveShadow = true;
    this.villa.add(ground);

    // Pool
    const poolGeometry = new THREE.BoxGeometry(4, 0.5, 3);
    const poolMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x00bfff,
      roughness: 0.1,
      metalness: 0.3,
      transparent: true,
      opacity: 0.8
    });
    const pool = new THREE.Mesh(poolGeometry, poolMaterial);
    pool.position.set(6, 0.25, 0);
    pool.receiveShadow = true;
    this.villa.add(pool);

    // Trees
    this.createTree(-6, 0, -4);
    this.createTree(7, 0, -5);
    this.createTree(-5, 0, 5);

    this.scene.add(this.villa);
  }

  createTree(x, y, z) {
    const tree = new THREE.Group();

    // Trunk
    const trunkGeometry = new THREE.CylinderGeometry(0.3, 0.4, 2, 8);
    const trunkMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x8b4513,
      roughness: 0.9
    });
    const trunk = new THREE.Mesh(trunkGeometry, trunkMaterial);
    trunk.position.y = 1;
    trunk.castShadow = true;
    tree.add(trunk);

    // Foliage
    const foliageGeometry = new THREE.SphereGeometry(1.5, 8, 8);
    const foliageMaterial = new THREE.MeshStandardMaterial({ 
      color: 0x228b22,
      roughness: 0.8
    });
    const foliage = new THREE.Mesh(foliageGeometry, foliageMaterial);
    foliage.position.y = 2.5;
    foliage.castShadow = true;
    tree.add(foliage);

    tree.position.set(x, y, z);
    this.villa.add(tree);
  }

  createParticles() {
    const particleCount = 100;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 30;
      positions[i + 1] = Math.random() * 15;
      positions[i + 2] = (Math.random() - 0.5) * 30;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.1,
      transparent: true,
      opacity: 0.6
    });

    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }

  addEventListeners() {
    // Mouse movement
    document.addEventListener('mousemove', (e) => {
      this.mouseX = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
    });

    // Window resize
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    // Smooth rotation based on mouse
    this.targetRotationX = this.mouseY * 0.1;
    this.targetRotationY = this.mouseX * 0.1;

    if (this.villa) {
      this.villa.rotation.x += (this.targetRotationX - this.villa.rotation.x) * 0.05;
      this.villa.rotation.y += (this.targetRotationY - this.villa.rotation.y) * 0.05;
      
      // Gentle floating animation
      this.villa.position.y = Math.sin(Date.now() * 0.001) * 0.2;
    }

    // Animate particles
    if (this.particles) {
      const positions = this.particles.geometry.attributes.position.array;
      for (let i = 1; i < positions.length; i += 3) {
        positions[i] += 0.01;
        if (positions[i] > 15) {
          positions[i] = 0;
        }
      }
      this.particles.geometry.attributes.position.needsUpdate = true;
    }

    this.renderer.render(this.scene, this.camera);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Only add 3D container to homepage hero section
  const heroSection = document.querySelector('section');
  const isHomepage = window.location.pathname === '/' || window.location.pathname === '/home';
  
  if (heroSection && isHomepage) {
    const container = document.createElement('div');
    container.id = 'hero-3d-container';
    container.style.cssText = 'position: absolute; inset: 0; z-index: 1; pointer-events: none;';
    heroSection.insertBefore(container, heroSection.firstChild);
    
    new Hero3D();
  }
});

// DOMIORA Three.js - 3D Floating Villa Scene

class FloatingVillaScene {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;
    
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.villa = null;
    this.particles = null;
    this.lights = [];
    this.clock = new THREE.Clock();
    this.mouse = new THREE.Vector2();
    this.targetRotation = new THREE.Vector2();
    
    this.init();
    this.createVilla();
    this.createParticles();
    this.createLights();
    this.addEventListeners();
    this.animate();
  }
  
  init() {
    // Scene
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x0a0a0a, 0.02);
    
    // Camera
    this.camera = new THREE.PerspectiveCamera(
      75,
      this.container.clientWidth / this.container.clientHeight,
      0.1,
      1000
    );
    this.camera.position.z = 15;
    this.camera.position.y = 5;
    
    // Renderer
    this.renderer = new THREE.WebGLRenderer({ 
      antialias: true, 
      alpha: true,
      powerPreference: "high-performance"
    });
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    this.container.appendChild(this.renderer.domElement);
    
    // Handle resize
    window.addEventListener('resize', () => this.onResize());
  }
  
  createVilla() {
    this.villa = new THREE.Group();
    
    // Main building - Modern geometric shape
    const mainGeometry = new THREE.BoxGeometry(8, 4, 6);
    const mainMaterial = new THREE.MeshStandardMaterial({
      color: 0x2a2a3a,
      metalness: 0.8,
      roughness: 0.2,
      envMapIntensity: 1
    });
    const mainBuilding = new THREE.Mesh(mainGeometry, mainMaterial);
    mainBuilding.position.y = 2;
    mainBuilding.castShadow = true;
    mainBuilding.receiveShadow = true;
    this.villa.add(mainBuilding);
    
    // Glass panels
    const glassGeometry = new THREE.BoxGeometry(7.5, 3, 0.1);
    const glassMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x88ccff,
      metalness: 0.1,
      roughness: 0.1,
      transmission: 0.9,
      thickness: 0.5,
      transparent: true,
      opacity: 0.6
    });
    
    // Front glass
    const frontGlass = new THREE.Mesh(glassGeometry, glassMaterial);
    frontGlass.position.set(0, 2.5, 3.05);
    this.villa.add(frontGlass);
    
    // Side glass
    const sideGlass = new THREE.Mesh(new THREE.BoxGeometry(0.1, 3, 5.5), glassMaterial);
    sideGlass.position.set(4.05, 2.5, 0);
    this.villa.add(sideGlass);
    
    // Roof - Modern flat design with slight angle
    const roofGeometry = new THREE.BoxGeometry(9, 0.3, 7);
    const roofMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a2a,
      metalness: 0.9,
      roughness: 0.1
    });
    const roof = new THREE.Mesh(roofGeometry, roofMaterial);
    roof.position.y = 4.15;
    roof.rotation.x = 0.05;
    roof.castShadow = true;
    this.villa.add(roof);
    
    // Pool/terrace on top
    const terraceGeometry = new THREE.BoxGeometry(6, 0.2, 4);
    const terraceMaterial = new THREE.MeshStandardMaterial({
      color: 0x4488ff,
      metalness: 0.3,
      roughness: 0.1,
      transparent: true,
      opacity: 0.8
    });
    const terrace = new THREE.Mesh(terraceGeometry, terraceMaterial);
    terrace.position.set(0, 4.4, 0);
    this.villa.add(terrace);
    
    // Decorative elements - Pillars
    const pillarGeometry = new THREE.CylinderGeometry(0.2, 0.2, 4.5, 8);
    const pillarMaterial = new THREE.MeshStandardMaterial({
      color: 0x3a3a4a,
      metalness: 0.7,
      roughness: 0.3
    });
    
    const pillarPositions = [
      [-3.8, 2.25, 2.8],
      [3.8, 2.25, 2.8],
      [-3.8, 2.25, -2.8],
      [3.8, 2.25, -2.8]
    ];
    
    pillarPositions.forEach(pos => {
      const pillar = new THREE.Mesh(pillarGeometry, pillarMaterial);
      pillar.position.set(...pos);
      pillar.castShadow = true;
      this.villa.add(pillar);
    });
    
    // Floating platform/base
    const platformGeometry = new THREE.CylinderGeometry(10, 8, 0.5, 32);
    const platformMaterial = new THREE.MeshStandardMaterial({
      color: 0x1a1a2e,
      metalness: 0.6,
      roughness: 0.4,
      transparent: true,
      opacity: 0.8
    });
    const platform = new THREE.Mesh(platformGeometry, platformMaterial);
    platform.position.y = -0.5;
    platform.receiveShadow = true;
    this.villa.add(platform);
    
    // Add glow rings around platform
    const ringGeometry = new THREE.TorusGeometry(9, 0.1, 16, 100);
    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0x7c3aed,
      transparent: true,
      opacity: 0.6
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = -0.3;
    this.villa.add(ring);
    
    this.scene.add(this.villa);
  }
  
  createParticles() {
    const particleCount = 200;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    
    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 30;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 30;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 30;
      
      // Purple/violet colors
      colors[i * 3] = 0.5 + Math.random() * 0.3; // R
      colors[i * 3 + 1] = 0.2 + Math.random() * 0.3; // G
      colors[i * 3 + 2] = 0.8 + Math.random() * 0.2; // B
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    
    const material = new THREE.PointsMaterial({
      size: 0.1,
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending
    });
    
    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }
  
  createLights() {
    // Ambient light
    const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
    this.scene.add(ambientLight);
    
    // Main directional light
    const mainLight = new THREE.DirectionalLight(0xffffff, 1);
    mainLight.position.set(10, 20, 10);
    mainLight.castShadow = true;
    mainLight.shadow.mapSize.width = 2048;
    mainLight.shadow.mapSize.height = 2048;
    this.scene.add(mainLight);
    this.lights.push(mainLight);
    
    // Purple accent lights
    const purpleLight1 = new THREE.PointLight(0x7c3aed, 2, 20);
    purpleLight1.position.set(-8, 5, 8);
    this.scene.add(purpleLight1);
    this.lights.push(purpleLight1);
    
    const purpleLight2 = new THREE.PointLight(0xa78bfa, 2, 20);
    purpleLight2.position.set(8, 5, -8);
    this.scene.add(purpleLight2);
    this.lights.push(purpleLight2);
    
    // Blue accent light
    const blueLight = new THREE.PointLight(0x3b82f6, 1.5, 15);
    blueLight.position.set(0, -5, 0);
    this.scene.add(blueLight);
    this.lights.push(blueLight);
  }
  
  addEventListeners() {
    document.addEventListener('mousemove', (e) => {
      this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    });
  }
  
  onResize() {
    if (!this.camera || !this.renderer) return;
    
    this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
  }
  
  animate() {
    requestAnimationFrame(() => this.animate());
    
    const time = this.clock.getElapsedTime();
    
    // Floating animation for villa
    if (this.villa) {
      this.villa.position.y = Math.sin(time * 0.5) * 0.5;
      this.villa.rotation.y = Math.sin(time * 0.2) * 0.1;
    }
    
    // Mouse interaction - smooth rotation
    this.targetRotation.x = this.mouse.y * 0.3;
    this.targetRotation.y = this.mouse.x * 0.3;
    
    if (this.villa) {
      this.villa.rotation.x += (this.targetRotation.x - this.villa.rotation.x) * 0.05;
      this.villa.rotation.y += (this.targetRotation.y - this.villa.rotation.y) * 0.05;
    }
    
    // Animate particles
    if (this.particles) {
      this.particles.rotation.y = time * 0.05;
      this.particles.rotation.x = time * 0.02;
    }
    
    // Animate lights
    this.lights.forEach((light, index) => {
      light.intensity = 1.5 + Math.sin(time * 2 + index) * 0.5;
    });
    
    // Camera subtle movement
    this.camera.position.x = Math.sin(time * 0.1) * 0.5;
    this.camera.position.y = 5 + Math.sin(time * 0.15) * 0.3;
    this.camera.lookAt(0, 2, 0);
    
    this.renderer.render(this.scene, this.camera);
  }
  
  destroy() {
    if (this.renderer) {
      this.renderer.dispose();
      this.container.removeChild(this.renderer.domElement);
    }
    window.removeEventListener('resize', this.onResize);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Check if we're on the home page
  if (document.querySelector('.hero-3d-container')) {
    new FloatingVillaScene('three-canvas');
  }
});

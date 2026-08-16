// DOMIORA 3D Loader with DOMIORA Logo
class Loader3D {
  constructor() {
    this.container = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.logo = null;
    this.particles = null;
    this.init();
  }

  init() {
    // Create loader container
    this.container = document.createElement('div');
    this.container.id = 'loader-3d';
    this.container.style.cssText = `
      position: fixed;
      inset: 0;
      background: linear-gradient(135deg, #71212d 0%, #0b3b5c 100%);
      z-index: 10000;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      transition: opacity 0.5s ease, visibility 0.5s ease;
    `;
    document.body.appendChild(this.container);

    // Scene setup
    this.scene = new THREE.Scene();
    
    // Camera setup
    this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    this.camera.position.set(0, 0, 10);
    
    // Renderer setup
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);
    
    // Lighting
    this.setupLighting();
    
    // Create DOMIORA logo
    this.createLogo();
    
    // Create particles
    this.createParticles();
    
    // Add loading text
    this.addLoadingText();
    
    // Event listeners
    this.addEventListeners();
    
    // Start animation
    this.animate();
    
    // Hide loader when page loads
    window.addEventListener('load', () => {
      setTimeout(() => {
        this.hideLoader();
      }, 1500);
    });
  }

  setupLighting() {
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    this.scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 5, 5);
    this.scene.add(directionalLight);
    
    const pointLight = new THREE.PointLight(0xd4af37, 0.5);
    pointLight.position.set(-5, -5, 5);
    this.scene.add(pointLight);
  }

  createLogo() {
    this.logo = new THREE.Group();
    
    // Create "D" letter
    this.createLetter('D', -2, 0, 0);
    
    // Create "O" letter
    this.createLetter('O', -0.5, 0, 0);
    
    // Create "M" letter
    this.createLetter('M', 1, 0, 0);
    
    // Create "I" letter
    this.createLetter('I', 2.5, 0, 0);
    
    // Create "O" letter
    this.createLetter('O', 3.5, 0, 0);
    
    // Create "R" letter
    this.createLetter('R', 5, 0, 0);
    
    // Create "A" letter
    this.createLetter('A', 6.5, 0, 0);
    
    this.scene.add(this.logo);
  }

  createLetter(char, x, y, z) {
    const letterGroup = new THREE.Group();
    
    // Create letter geometry based on character
    switch(char) {
      case 'D':
        this.createD(letterGroup);
        break;
      case 'O':
        this.createO(letterGroup);
        break;
      case 'M':
        this.createM(letterGroup);
        break;
      case 'I':
        this.createI(letterGroup);
        break;
      case 'R':
        this.createR(letterGroup);
        break;
      case 'A':
        this.createA(letterGroup);
        break;
    }
    
    letterGroup.position.set(x, y, z);
    this.logo.add(letterGroup);
  }

  createD(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    // Vertical line
    const lineGeometry = new THREE.BoxGeometry(0.3, 2, 0.3);
    const line = new THREE.Mesh(lineGeometry, material);
    line.position.set(-0.5, 0, 0);
    group.add(line);
    
    // Curve
    const curveGeometry = new THREE.TorusGeometry(0.8, 0.15, 16, 32, Math.PI);
    const curve = new THREE.Mesh(curveGeometry, material);
    curve.position.set(0.3, 0, 0);
    curve.rotation.z = Math.PI / 2;
    group.add(curve);
  }

  createO(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    const geometry = new THREE.TorusGeometry(0.8, 0.15, 16, 32);
    const torus = new THREE.Mesh(geometry, material);
    group.add(torus);
  }

  createM(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    const lineGeometry = new THREE.BoxGeometry(0.3, 2, 0.3);
    
    // Left line
    const leftLine = new THREE.Mesh(lineGeometry, material);
    leftLine.position.set(-0.8, 0, 0);
    group.add(leftLine);
    
    // Right line
    const rightLine = new THREE.Mesh(lineGeometry, material);
    rightLine.position.set(0.8, 0, 0);
    group.add(rightLine);
    
    // Middle V
    const vGeometry = new THREE.BoxGeometry(0.3, 1.2, 0.3);
    const leftV = new THREE.Mesh(vGeometry, material);
    leftV.position.set(-0.4, 0.4, 0);
    leftV.rotation.z = 0.3;
    group.add(leftV);
    
    const rightV = new THREE.Mesh(vGeometry, material);
    rightV.position.set(0.4, 0.4, 0);
    rightV.rotation.z = -0.3;
    group.add(rightV);
  }

  createI(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    const lineGeometry = new THREE.BoxGeometry(0.3, 2, 0.3);
    const line = new THREE.Mesh(lineGeometry, material);
    group.add(line);
  }

  createR(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    // Vertical line
    const lineGeometry = new THREE.BoxGeometry(0.3, 2, 0.3);
    const line = new THREE.Mesh(lineGeometry, material);
    line.position.set(-0.5, 0, 0);
    group.add(line);
    
    // Top curve
    const curveGeometry = new THREE.TorusGeometry(0.6, 0.15, 16, 32, Math.PI * 0.7);
    const curve = new THREE.Mesh(curveGeometry, material);
    curve.position.set(0.2, 0.6, 0);
    curve.rotation.z = Math.PI / 2;
    group.add(curve);
    
    // Diagonal
    const diagonalGeometry = new THREE.BoxGeometry(0.3, 1, 0.3);
    const diagonal = new THREE.Mesh(diagonalGeometry, material);
    diagonal.position.set(0.2, -0.3, 0);
    diagonal.rotation.z = 0.5;
    group.add(diagonal);
  }

  createA(group) {
    const material = new THREE.MeshStandardMaterial({ 
      color: 0xffffff,
      roughness: 0.3,
      metalness: 0.7
    });
    
    const lineGeometry = new THREE.BoxGeometry(0.3, 2, 0.3);
    
    // Left line
    const leftLine = new THREE.Mesh(lineGeometry, material);
    leftLine.position.set(-0.5, 0, 0);
    leftLine.rotation.z = 0.2;
    group.add(leftLine);
    
    // Right line
    const rightLine = new THREE.Mesh(lineGeometry, material);
    rightLine.position.set(0.5, 0, 0);
    rightLine.rotation.z = -0.2;
    group.add(rightLine);
    
    // Crossbar
    const crossbarGeometry = new THREE.BoxGeometry(0.8, 0.3, 0.3);
    const crossbar = new THREE.Mesh(crossbarGeometry, material);
    crossbar.position.set(0, -0.3, 0);
    group.add(crossbar);
  }

  createParticles() {
    const particleCount = 100;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    
    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 20;
      positions[i + 1] = (Math.random() - 0.5) * 20;
      positions[i + 2] = (Math.random() - 0.5) * 20;
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    
    const material = new THREE.PointsMaterial({
      color: 0xd4af37,
      size: 0.1,
      transparent: true,
      opacity: 0.6
    });
    
    this.particles = new THREE.Points(geometry, material);
    this.scene.add(this.particles);
  }

  addLoadingText() {
    const text = document.createElement('div');
    text.textContent = 'DOMIORA';
    text.style.cssText = `
      position: absolute;
      bottom: 20%;
      font-family: 'Montserrat', sans-serif;
      font-size: 2rem;
      font-weight: 800;
      color: white;
      letter-spacing: 0.5em;
      animation: pulse 1.5s ease-in-out infinite;
    `;
    this.container.appendChild(text);
    
    const style = document.createElement('style');
    style.textContent = `
      @keyframes pulse {
        0%, 100% { opacity: 0.5; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.05); }
      }
    `;
    document.head.appendChild(style);
  }

  addEventListeners() {
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  animate() {
    requestAnimationFrame(() => this.animate);
    
    // Rotate logo
    if (this.logo) {
      this.logo.rotation.y += 0.01;
      this.logo.position.y = Math.sin(Date.now() * 0.002) * 0.2;
    }
    
    // Rotate particles
    if (this.particles) {
      this.particles.rotation.y += 0.002;
      this.particles.rotation.x += 0.001;
    }
    
    this.renderer.render(this.scene, this.camera);
  }

  hideLoader() {
    this.container.style.opacity = '0';
    this.container.style.visibility = 'hidden';
    
    setTimeout(() => {
      this.container.remove();
    }, 500);
  }
}

// Initialize loader
new Loader3D();

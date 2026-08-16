// DOMIORA 3D Property Cards - Premium Depth and Rotation Effects
class Card3D {
  constructor(card) {
    this.card = card;
    this.tiltX = 0;
    this.tiltY = 0;
    this.targetTiltX = 0;
    this.targetTiltY = 0;
    this.init();
  }

  init() {
    this.card.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    this.card.addEventListener('mouseleave', () => this.handleMouseLeave());
    this.card.addEventListener('mouseenter', () => this.handleMouseEnter());
    
    // Add 3D container
    this.card.style.transformStyle = 'preserve-3d';
    this.card.style.perspective = '1000px';
  }

  handleMouseMove(e) {
    const rect = this.card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;
    
    // Calculate rotation (max 15 degrees)
    this.targetTiltX = ((y - centerY) / centerY) * -15;
    this.targetTiltY = ((x - centerX) / centerX) * 15;
  }

  handleMouseEnter() {
    this.card.style.transition = 'transform 0.1s ease-out';
  }

  handleMouseLeave() {
    this.targetTiltX = 0;
    this.targetTiltY = 0;
    this.card.style.transition = 'transform 0.5s ease-out';
  }

  update() {
    // Smooth interpolation
    this.tiltX += (this.targetTiltX - this.tiltX) * 0.1;
    this.tiltY += (this.targetTiltY - this.tiltY) * 0.1;
    
    // Apply transform with depth effect
    const depth = Math.abs(this.tiltX) + Math.abs(this.tiltY);
    const scale = 1 + depth * 0.005;
    
    this.card.style.transform = `
      perspective(1000px)
      rotateX(${this.tiltX}deg)
      rotateY(${this.tiltY}deg)
      scale(${scale})
      translateZ(${depth}px)
    `;
  }
}

// Initialize all property cards
class Cards3DManager {
  constructor() {
    this.cards = [];
    this.init();
  }

  init() {
    // Only apply 3D effects on listing pages, not detail pages
    const isDetailPage = window.location.pathname.includes('/proprietes/') && window.location.pathname.split('/').length > 2;
    
    if (!isDetailPage) {
      // Find all property cards
      const cardElements = document.querySelectorAll('.property-card, [class*="property"]');
      
      cardElements.forEach(card => {
        this.cards.push(new Card3D(card));
      });

      // Start animation loop
      this.animate();
    }
  }

  animate() {
    this.cards.forEach(card => card.update());
    requestAnimationFrame(() => this.animate());
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new Cards3DManager();
});

// Add dynamic shadow effect to cards
function addDynamicShadows() {
  const cards = document.querySelectorAll('.property-card, [class*="property"]');
  
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      
      const shadowX = (x - centerX) / 20;
      const shadowY = (y - centerY) / 20;
      
      card.style.boxShadow = `
        ${shadowX}px ${shadowY}px 30px rgba(113, 33, 45, 0.3),
        ${shadowX * 0.5}px ${shadowY * 0.5}px 60px rgba(113, 33, 45, 0.2)
      `;
    });
    
    card.addEventListener('mouseleave', () => {
      card.style.boxShadow = '';
    });
  });
}

document.addEventListener('DOMContentLoaded', addDynamicShadows);

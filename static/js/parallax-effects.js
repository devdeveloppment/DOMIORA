// DOMIORA Parallax Effects for Homepage
class ParallaxEffects {
  constructor() {
    this.init();
  }

  init() {
    this.setupParallaxScroll();
    this.setupParallaxMouse();
    this.setupParallaxHero();
    this.setupParallaxCards();
  }

  setupParallaxScroll() {
    // Parallax scroll effect for background elements
    const parallaxElements = document.querySelectorAll('[data-parallax]');
    
    window.addEventListener('scroll', () => {
      const scrollY = window.scrollY;
      
      parallaxElements.forEach(element => {
        const speed = parseFloat(element.getAttribute('data-parallax')) || 0.5;
        const yPos = -(scrollY * speed);
        element.style.transform = `translateY(${yPos}px)`;
      });
    });
  }

  setupParallaxMouse() {
    // Parallax mouse movement effect
    const parallaxContainer = document.querySelector('[data-parallax-mouse]');
    
    if (parallaxContainer) {
      parallaxContainer.addEventListener('mousemove', (e) => {
        const rect = parallaxContainer.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        
        const elements = parallaxContainer.querySelectorAll('[data-depth]');
        elements.forEach(element => {
          const depth = parseFloat(element.getAttribute('data-depth')) || 1;
          const moveX = x * depth * 30;
          const moveY = y * depth * 30;
          
          element.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });
      });
      
      parallaxContainer.addEventListener('mouseleave', () => {
        const elements = parallaxContainer.querySelectorAll('[data-depth]');
        elements.forEach(element => {
          element.style.transform = 'translate(0, 0)';
        });
      });
    }
  }

  setupParallaxHero() {
    // Parallax effect for hero section
    const heroSection = document.querySelector('section');
    const heroImage = heroSection?.querySelector('img');
    
    if (heroSection && heroImage) {
      window.addEventListener('scroll', () => {
        const scrollY = window.scrollY;
        const heroHeight = heroSection.offsetHeight;
        
        if (scrollY < heroHeight) {
          const translateY = scrollY * 0.4;
          const scale = 1 + (scrollY / heroHeight) * 0.1;
          
          heroImage.style.transform = `translateY(${translateY}px) scale(${scale})`;
        }
      });
    }
  }

  setupParallaxCards() {
    // Parallax effect for cards
    const cards = document.querySelectorAll('.property-card, [data-parallax-card]');
    
    cards.forEach(card => {
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        
        const image = card.querySelector('img');
        if (image) {
          const moveX = x * 20;
          const moveY = y * 20;
          image.style.transform = `translate(${moveX}px, ${moveY}px) scale(1.1)`;
        }
      });
      
      card.addEventListener('mouseleave', () => {
        const image = card.querySelector('img');
        if (image) {
          image.style.transform = 'translate(0, 0) scale(1)';
        }
      });
    });
  }
}

// Initialize parallax effects
document.addEventListener('DOMContentLoaded', () => {
  new ParallaxEffects();
});

// Add parallax attributes to elements
function addParallaxAttributes() {
  // Add parallax to hero background
  const heroSection = document.querySelector('section');
  if (heroSection) {
    const heroImage = heroSection.querySelector('img');
    if (heroImage) {
      heroImage.setAttribute('data-parallax', '0.3');
    }
  }
  
  // Add parallax to stat cards
  const statCards = document.querySelectorAll('.stat-card, [class*="stat"]');
  statCards.forEach((card, index) => {
    card.setAttribute('data-parallax', `0.${index + 1}`);
  });
}

document.addEventListener('DOMContentLoaded', addParallaxAttributes);

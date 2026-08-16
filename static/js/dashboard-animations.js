// DOMIORA Dashboard Animations - Floating Cards and Animated Counters
class DashboardAnimations {
  constructor() {
    this.init();
  }

  init() {
    this.animateCounters();
    this.animateFloatingCards();
    this.animateProgressBars();
    this.animateCharts();
  }

  // Animated counters
  animateCounters() {
    const counters = document.querySelectorAll('[data-counter]');
    
    counters.forEach(counter => {
      const target = parseInt(counter.getAttribute('data-counter'));
      const duration = 2000; // 2 seconds
      const steps = 60;
      const increment = target / steps;
      let current = 0;
      
      const updateCounter = () => {
        current += increment;
        if (current < target) {
          counter.textContent = Math.floor(current).toLocaleString();
          requestAnimationFrame(updateCounter);
        } else {
          counter.textContent = target.toLocaleString();
        }
      };
      
      // Start animation when element is in view
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            updateCounter();
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.5 });
      
      observer.observe(counter);
    });
  }

  // Floating cards effect
  animateFloatingCards() {
    const cards = document.querySelectorAll('.dashboard-card, .stat-card, .info-card');
    
    cards.forEach((card, index) => {
      // Add floating animation with different delays
      card.style.animation = `float 6s ease-in-out ${index * 0.2}s infinite`;
      
      // Add 3D tilt effect on hover
      card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const rotateX = ((y - centerY) / centerY) * -5;
        const rotateY = ((x - centerX) / centerX) * 5;
        
        card.style.transform = `
          perspective(1000px)
          rotateX(${rotateX}deg)
          rotateY(${rotateY}deg)
          scale(1.02)
          translateZ(10px)
        `;
      });
      
      card.addEventListener('mouseleave', () => {
        card.style.transform = '';
      });
    });
  }

  // Animated progress bars
  animateProgressBars() {
    const progressBars = document.querySelectorAll('[data-progress]');
    
    progressBars.forEach(bar => {
      const target = parseInt(bar.getAttribute('data-progress'));
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            bar.style.width = '0%';
            bar.style.transition = 'width 1.5s ease-out';
            
            setTimeout(() => {
              bar.style.width = `${target}%`;
            }, 100);
            
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.5 });
      
      observer.observe(bar);
    });
  }

  // Animated charts
  animateCharts() {
    const chartElements = document.querySelectorAll('.chart-container, [data-chart]');
    
    chartElements.forEach(chart => {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            chart.style.opacity = '0';
            chart.style.transform = 'translateY(20px)';
            
            gsap.to(chart, {
              opacity: 1,
              y: 0,
              duration: 0.8,
              ease: 'power2.out'
            });
            
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.3 });
      
      observer.observe(chart);
    });
  }
}

// Initialize dashboard animations
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('.dashboard, [class*="dashboard"]')) {
    new DashboardAnimations();
  }
});

// Add glassmorphism effect to dashboard cards
function addGlassmorphism() {
  const cards = document.querySelectorAll('.dashboard-card, .stat-card');
  
  cards.forEach(card => {
    card.style.background = 'rgba(255, 255, 255, 0.7)';
    card.style.backdropFilter = 'blur(10px)';
    card.style.border = '1px solid rgba(255, 255, 255, 0.2)';
    card.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.1)';
  });
}

// Add neumorphism effect to specific elements
function addNeumorphism() {
  const elements = document.querySelectorAll('.neumorphism, [data-neumorphism]');
  
  elements.forEach(element => {
    element.style.background = '#f0f0f0';
    element.style.boxShadow = '8px 8px 16px #d1d1d1, -8px -8px 16px #ffffff';
    element.style.borderRadius = '20px';
  });
}

// Initialize effects
document.addEventListener('DOMContentLoaded', () => {
  addGlassmorphism();
  addNeumorphism();
});

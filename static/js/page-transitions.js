// DOMIORA Fluid Page Transition Animations
class PageTransitions {
  constructor() {
    this.init();
  }

  init() {
    this.setupPageTransitions();
    this.setupLinkInterceptions();
    this.setupFormSubmissions();
  }

  setupPageTransitions() {
    // Add transition overlay
    const overlay = document.createElement('div');
    overlay.className = 'page-transition-overlay';
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      background: linear-gradient(135deg, #71212d 0%, #0b3b5c 100%);
      z-index: 9999;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.5s ease;
    `;
    document.body.appendChild(overlay);

    // Animate page load
    window.addEventListener('load', () => {
      overlay.style.opacity = '1';
      setTimeout(() => {
        overlay.style.opacity = '0';
        this.animatePageContent();
      }, 300);
    });
  }

  setupLinkInterceptions() {
    // Intercept internal links for smooth transitions
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');
      
      if (link && this.isInternalLink(link)) {
        e.preventDefault();
        this.transitionToPage(link.href);
      }
    });
  }

  setupFormSubmissions() {
    // Animate form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
      form.addEventListener('submit', () => {
        this.animateFormSubmission(form);
      });
    });
  }

  isInternalLink(link) {
    const href = link.getAttribute('href');
    return href && 
           href.startsWith('/') && 
           !href.startsWith('#') &&
           !link.hasAttribute('download') &&
           !link.hasAttribute('target');
  }

  transitionToPage(url) {
    const overlay = document.querySelector('.page-transition-overlay');
    
    // Fade out
    overlay.style.opacity = '1';
    
    setTimeout(() => {
      window.location.href = url;
    }, 500);
  }

  animatePageContent() {
    // Animate main content with staggered effect
    const main = document.querySelector('main');
    if (!main) return;

    const children = main.children;
    gsap.fromTo(children, 
      { opacity: 0, y: 30 },
      { 
        opacity: 1, 
        y: 0, 
        duration: 0.6, 
        stagger: 0.1, 
        ease: 'power2.out' 
      }
    );
  }

  animateFormSubmission(form) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;

    // Add loading state
    button.classList.add('loading');
    button.disabled = true;
  }
}

// Initialize page transitions
document.addEventListener('DOMContentLoaded', () => {
  new PageTransitions();
});

// Add smooth scroll behavior
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    e.preventDefault();
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      gsap.to(window, {
        duration: 1,
        scrollTo: { y: target, offsetY: 80 },
        ease: 'power2.inOut'
      });
    }
  });
});

// GSAP ScrollTo plugin
gsap.registerPlugin(ScrollToPlugin = {
  scrollTo: {
    y: (value) => window.scrollTo({ top: value, behavior: 'smooth' })
  }
});

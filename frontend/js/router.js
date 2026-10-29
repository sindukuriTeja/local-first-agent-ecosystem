/**
 * Hash-based Single Page App (SPA) Router
 * Routes format: #/loans, #/loans/LN-001, #/home, etc.
 */
import { state } from './services/state.js';

export class Router {
  constructor(routes = {}, onRouteChange = null) {
    this.routes = routes;
    this.onRouteChange = onRouteChange;
    this.currentRoute = '';
    this.currentParams = {};

    window.addEventListener('hashchange', () => this.handleRoute());
  }

  init() {
    if (!window.location.hash) {
      window.location.hash = '#/home';
    } else {
      this.handleRoute();
    }
  }

  handleRoute() {
    const rawHash = window.location.hash.slice(1) || '/home';
    const [pathPart, queryPart] = rawHash.split('?');
    const segments = pathPart.split('/').filter(Boolean);

    let matchedRoute = null;
    let params = {};

    // Match routes
    for (const pattern in this.routes) {
      const patternSegments = pattern.split('/').filter(Boolean);
      if (patternSegments.length !== segments.length) continue;

      let match = true;
      const candidateParams = {};

      for (let i = 0; i < patternSegments.length; i++) {
        if (patternSegments[i].startsWith(':')) {
          const paramName = patternSegments[i].slice(1);
          candidateParams[paramName] = segments[i];
        } else if (patternSegments[i] !== segments[i]) {
          match = false;
          break;
        }
      }

      if (match) {
        matchedRoute = pattern;
        params = candidateParams;
        break;
      }
    }

    // Default fallback route
    if (!matchedRoute) {
      matchedRoute = this.routes['*'] ? '*' : '/home';
    }

    this.currentRoute = matchedRoute;
    this.currentParams = params;

    // Check Role Access
    if (!this.checkRoleAccess(pathPart)) {
      if (this.onRouteChange) {
        this.onRouteChange('blocked', { path: pathPart, requiredRole: 'Authorized Role' });
      }
      return;
    }

    const handler = this.routes[matchedRoute];
    if (handler && this.onRouteChange) {
      this.onRouteChange(matchedRoute, params, handler);
    }
  }

  checkRoleAccess(path) {
    const role = state.currentRole;
    if (role === 'Administrator' || role === 'admin') return true; // Admins see everything

    // Specific role rules from Section 4 & Role mappings
    if (role === 'External counsel') {
      return path === '/home' || path === '/ask' || path.startsWith('/matters') || path.startsWith('/documents') || path === '/login' || path === '/profile';
    }
    if (role === 'Manager / Board member' || role === 'Management' || role === 'management') {
      return path === '/ask' || (!path.startsWith('/security') && !path.startsWith('/admin') && !path.startsWith('/research') && !path.startsWith('/drafting'));
    }
    if (role === 'Lawyer' || role === 'Advocate' || role === 'advocate') {
      return path === '/home' || path === '/ask' || path.startsWith('/matters') || path.startsWith('/research') || path.startsWith('/drafting') || path.startsWith('/documents') || path.startsWith('/approvals') || path.startsWith('/calendar') || path === '/profile';
    }
    if (role === 'Tax team member') {
      return path === '/home' || path === '/ask' || path.startsWith('/tax') || path.startsWith('/drafting') || path.startsWith('/documents') || path.startsWith('/calendar') || path === '/profile';
    }
    if (role === 'Company secretary') {
      return path === '/home' || path === '/ask' || path.startsWith('/companies') || path.startsWith('/documents') || path.startsWith('/calendar') || path === '/profile';
    }
    if (role === 'Finance team member' || role === 'Auditor' || role === 'auditor') {
      return path === '/home' || path === '/ask' || path.startsWith('/loans') || path.startsWith('/land') || path.startsWith('/documents') || path.startsWith('/calendar') || path.startsWith('/reports') || path.startsWith('/security') || path === '/profile';
    }
    if (role === 'Staff member' || role === 'Internal Employee' || role === 'employee') {
      return path === '/home' || path === '/ask' || path.startsWith('/documents') || path.startsWith('/calendar') || path.startsWith('/notifications') || path.startsWith('/matters') || path.startsWith('/tax') || path === '/profile';
    }
    if (role === 'Client' || role === 'client') {
      return path === '/home' || path === '/ask' || path.startsWith('/documents') || path.startsWith('/matters') || path.startsWith('/approvals') || path === '/profile';
    }
    if (role === 'Tenant or Buyer' || role === 'tenant') {
      return path === '/home' || path === '/ask' || path.startsWith('/land') || path.startsWith('/documents') || path === '/profile';
    }

    return true;
  }

  navigate(hash) {
    window.location.hash = hash.startsWith('#') ? hash : `#${hash}`;
  }
}

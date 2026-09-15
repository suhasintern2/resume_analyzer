You are working on an existing resume-assessment platform.

TASK:
Convert the existing frontend UI from plain HTML/CSS/JavaScript to React using Vite.

IMPORTANT:
This is a MIGRATION, NOT a UI redesign.

The existing UI is already approved. The React version must visually match the existing UI as closely as possible.

DO NOT redesign, modernize, restyle, rearrange, or "improve" the interface.

==================================================
1. PRIMARY OBJECTIVE
==================================================

Convert the current frontend implementation to:

- React
- Vite
- JavaScript
- JSX
- Existing CSS where possible

Keep the existing backend/API architecture completely unchanged.

The objective is:

CURRENT:
HTML + CSS + JavaScript
        ↓
NEW:
React + Vite + JavaScript + CSS

The UI, behaviour, layout, styling, content, and user experience should remain the same.

==================================================
2. BEFORE CHANGING ANYTHING
==================================================

First inspect the entire existing frontend.

Understand:

- Current HTML structure
- CSS files
- JavaScript files
- DOM manipulation
- Event handlers
- Forms
- Buttons
- Inputs
- API calls
- Loading states
- Error states
- File upload behaviour
- Navigation
- Modals
- Tables
- Cards
- Responsive behaviour
- Assets
- Fonts
- Icons
- Images
- Existing animations/transitions

Do NOT immediately start rewriting.

First determine:

1. What the current UI contains
2. How the UI behaves
3. Which JavaScript functions manipulate the DOM
4. Which state currently exists
5. Which API endpoints are being called
6. Which CSS rules control each part of the UI

Then create a short migration plan before implementing.

==================================================
3. EXACT UI PRESERVATION
==================================================

The following must NOT change unless technically required by React:

- Page layout
- Widths
- Heights
- Margins
- Padding
- Spacing
- Typography
- Font sizes
- Font weights
- Colors
- Borders
- Border radius
- Shadows
- Buttons
- Icons
- Images
- Tables
- Cards
- Forms
- Input appearance
- Navigation
- Header
- Footer
- Alignment
- Responsive behaviour
- Hover states
- Focus states
- Loading states
- Error states
- Empty states
- Text/content
- User flow

Do NOT introduce a new design system.

Do NOT introduce Tailwind CSS.

Do NOT introduce Material UI.

Do NOT introduce Bootstrap.

Do NOT replace the existing CSS with another styling framework.

Reuse the existing CSS wherever practical.

If CSS selectors need to change because of JSX, make the smallest possible change.

==================================================
4. REACT ARCHITECTURE
==================================================

Convert the UI into sensible React components.

Do not create hundreds of unnecessary components.

Use components where there is a real UI responsibility or reusable element.

For example:

src/
├── components/
│   ├── Header.jsx
│   ├── ResumeUpload.jsx
│   ├── QuestionCard.jsx
│   ├── AnswerBox.jsx
│   └── ...
│
├── pages/
│   ├── ...
│
├── services/
│   └── api.js
│
├── assets/
│
├── App.jsx
├── main.jsx
└── index.css

Adjust this structure based on the actual existing application.

Do not force this exact folder structure if another structure is more appropriate.

==================================================
5. REACT STATE
==================================================

Replace manual DOM state manipulation with React state where appropriate.

For example, instead of:

document.querySelector(...)
element.innerHTML = ...
element.style.display = ...
element.disabled = ...

use React state and conditional rendering.

Use:

- useState
- useEffect
- props
- event handlers
- conditional rendering
- lists and keys

only where actually required.

Do not introduce unnecessary state management libraries.

Do not add Redux, Zustand, MobX, etc. unless the existing application genuinely requires it.

Keep the implementation simple.

==================================================
6. EXISTING FUNCTIONALITY MUST CONTINUE TO WORK
==================================================

This is critical.

Do NOT only reproduce the appearance.

All existing functionality must continue to work.

Preserve:

- API requests
- API endpoints
- HTTP methods
- Request payloads
- Response handling
- File uploads
- Authentication behaviour
- Error handling
- Loading behaviour
- Form validation
- Navigation
- Existing business logic
- Existing backend integration

DO NOT modify the backend unless absolutely necessary for the React migration.

The backend architecture must remain unchanged.

==================================================
7. API LAYER
==================================================

If the current frontend directly calls backend APIs, preserve those API calls.

Prefer moving API-related code into a small service layer such as:

src/services/api.js

But do not change the API contract.

For example:

CURRENT:

fetch("/api/resume/upload", ...)

should continue calling:

/api/resume/upload

Do NOT rename endpoints.

Do NOT change request/response structures.

Do NOT create fake/mock APIs unless the existing application already uses mocks.

==================================================
8. FILE UPLOAD
==================================================

The platform supports resume upload.

Preserve the existing:

- File picker
- Accepted file types
- File validation
- Upload behaviour
- Progress/loading state
- Error messages
- Backend request
- Result handling

Do not replace the upload implementation with a different library unless necessary.

==================================================
9. PERFORMANCE
==================================================

The current HTML/CSS UI is already lightweight.

Treat the current implementation as the performance baseline.

Do NOT assume React will automatically be faster.

Avoid unnecessary:

- dependencies
- libraries
- re-renders
- large assets
- client-side processing
- duplicate API requests
- unnecessary effects
- unnecessary state

Do not add libraries simply because they are popular.

The React migration should not introduce obvious performance regressions.

After implementation, compare:

- Network requests
- Number of loaded assets
- JavaScript bundle size
- DOMContentLoaded
- page load/finish time
- unnecessary API requests

against the current implementation where possible.

==================================================
10. DO NOT CHANGE THE BACKEND ARCHITECTURE
==================================================

The existing platform architecture must remain intact.

React is only replacing the frontend layer.

Target architecture:

                React + Vite
                     │
                     │ HTTP/API
                     ▼
               Node / Express
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       MongoDB   PDF Service  Vector Service
                             
                     │
                     ▼
              Evaluation Engine

Do not convert the backend to another framework.

Do not introduce microservices.

Do not change MongoDB.

Do not change the PDF extraction service.

Do not change the vector-search architecture.

Do not change the evaluation architecture.

==================================================
11. DO NOT ADD FEATURES
==================================================

Do not add:

- New dashboards
- New animations
- New pages
- Dark mode
- New navigation
- New authentication flows
- New AI features
- New UI components that don't already exist
- New business logic
- New validation rules
- New backend functionality

unless they already exist in the current implementation.

This task is strictly:

EXISTING UI + EXISTING FUNCTIONALITY
                ↓
         React implementation

==================================================
12. VISUAL VALIDATION
==================================================

After implementation, run the application and compare the React UI against the original UI.

Check:

- Overall layout
- Header
- Navigation
- Typography
- Spacing
- Cards
- Buttons
- Forms
- Tables
- Upload area
- Question area
- Results
- Responsive layout
- Hover/focus states
- Loading states
- Error states

If screenshots or browser inspection are available, use them.

The React implementation should be visually indistinguishable from the original UI for normal usage.

If something looks different, fix the React/CSS implementation instead of redesigning the original.

==================================================
13. MIGRATION RULE
==================================================

Do not rewrite working business logic unnecessarily.

Prefer:

REUSE → ADAPT → REFACTOR ONLY WHEN NECESSARY

rather than:

REWRITE EVERYTHING FROM SCRATCH

The migration should preserve working behaviour while moving UI rendering and state management into React.

==================================================
14. CODE QUALITY
==================================================

Use clean, understandable React.

Follow normal React conventions:

- Functional components
- Hooks
- Props
- Meaningful component names
- No unnecessary class components
- No direct DOM manipulation unless genuinely required
- No duplicated UI logic
- No unnecessary abstractions

Do not over-engineer the project.

This is an MVP/internal corporate platform, not a framework experiment.

==================================================
15. IMPORTANT REACT RULE
==================================================

Do not use React merely as a replacement syntax for HTML.

Actually convert the UI architecture to React.

For example, avoid simply putting the entire existing HTML inside one enormous App.jsx.

Identify meaningful UI components and move state/event behaviour into React.

However, do not split every <div> into its own component.

Use practical component boundaries.

==================================================
16. EXPECTED FINAL RESULT
==================================================

At the end:

1. The application runs using Vite.
2. The frontend is implemented using React.
3. Existing CSS is preserved as much as possible.
4. Existing UI looks the same.
5. Existing functionality works.
6. Existing API contracts remain unchanged.
7. Backend architecture remains unchanged.
8. No unnecessary dependencies are introduced.
9. No unnecessary features are added.
10. The code is organized into sensible React components.
11. React state replaces appropriate manual DOM manipulation.
12. The UI is validated against the original implementation.

==================================================
17. FINAL REPORT
==================================================

After completing the migration, provide a concise report containing:

### Files Changed
List the important files created/modified.

### Components Created
List the main React components.

### Existing Functionality Preserved
List the major functionality verified.

### API Changes
Clearly state:

"None"

if no backend/API changes were required.

### CSS Changes
Explain only the CSS changes required for React compatibility.

### Dependencies Added
List only dependencies actually added.

### Performance Comparison
Provide the available before/after measurements.

### Known Differences
If anything could not be made exactly identical, explicitly state what and why.

Do not claim the migration is complete until the application has actually been run and checked.
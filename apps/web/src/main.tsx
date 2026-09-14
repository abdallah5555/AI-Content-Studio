import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { bootstrapRuntime } from './runtime';
import './styles.css';
import './review.css';
import './reference.css';
import './output.css';
import './history.css';
import './intelligence.css';
import './avatar.css';
import './settings.css';
import './runtime.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

void bootstrapRuntime();

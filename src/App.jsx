import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import Tabs from './components/common/Tabs';
import CustomerPortal from './components/customer/CustomerPortal';
import AgentPortal from './components/agent/AgentPortal';
import HelpDeskPortal from './components/helpdesk/HelpDeskPortal';
import './styles/App.css';

const TABS = [
  { id: 'customer', label: 'Customer Portal' },
  { id: 'agent', label: 'Agent Portal' },
  { id: 'helpdesk', label: 'HelpDesk' },
];

function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

function AppShell() {
  const [activeTab, setActiveTab] = useState('customer');

  return (
    <div className="app-container">
      <header className="app-header">
        <h1 className="app-title">Advanced Support Dashboard</h1>
        <p className="app-subtitle">Incident Management System</p>
      </header>
      <Tabs tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="app-main">
        <section hidden={activeTab !== 'customer'} aria-hidden={activeTab !== 'customer'}>
          <CustomerPortal />
        </section>
        <section hidden={activeTab !== 'agent'} aria-hidden={activeTab !== 'agent'}>
          <AgentPortal />
        </section>
        <section hidden={activeTab !== 'helpdesk'} aria-hidden={activeTab !== 'helpdesk'}>
          <HelpDeskPortal />
        </section>
      </main>
    </div>
  );
}

export default App;

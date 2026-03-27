import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import Tabs from './components/common/Tabs';
import CustomerPortal from './components/customer/CustomerPortal';
import AgentPortal from './components/agent/AgentPortal';
import './styles/App.css';

const TABS = [
  { id: 'customer', label: 'Customer Portal' },
  { id: 'agent', label: 'Agent Portal' },
];

function App() {
  const [activeTab, setActiveTab] = useState('customer');

  return (
    <AuthProvider>
      <div className="app-container">
        <header className="app-header">
          <h1 className="app-title">Advanced Support Dashboard</h1>
          <p className="app-subtitle">Incident Management System</p>
        </header>
        <Tabs tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="app-main">
          {activeTab === 'customer' ? <CustomerPortal /> : <AgentPortal />}
        </main>
      </div>
    </AuthProvider>
  );
}

export default App;

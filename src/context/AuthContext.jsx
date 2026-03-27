import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

function AuthProvider({ children }) {
  const [agentUser, setAgentUser] = useState(null);

  async function login(uid, password) {
    const response = await fetch(`${API_BASE_URL}/api/agents/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message || data.error || 'Login failed');
    }

    setAgentUser(data);
  }

  function logout() {
    setAgentUser(null);
  }

  return (
    <AuthContext.Provider value={{ agentUser, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function useAuth() {
  return useContext(AuthContext);
}

export { AuthContext, AuthProvider, useAuth };

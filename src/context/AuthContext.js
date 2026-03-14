import React, { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [agentUser, setAgentUser] = useState(null);

  async function login(uid, password) {
    const response = await fetch('http://localhost:5000/api/agents/login', {
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

import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useState } from 'react';
import { SpaceDetectionPage } from './pages/SpaceDetectionPage';
import { HistoryPage } from './pages/HistoryPage';
import { StatsPage } from './pages/StatsPage';
import { AlertsPage } from './pages/AlertsPage';
import { MultiCameraPage } from './pages/MultiCameraPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { AccountPage } from './pages/AccountPage';
import { StreamHostPage } from './pages/StreamHostPage';
import { MultiStreamHostPage } from './pages/MultiStreamHostPage';
import { StreamViewerPageESP32 as StreamViewerPage } from './pages/StreamViewerPageESP32';
import { MultiStreamViewerPage } from './pages/MultiStreamViewerPage';
import { PlateHistoryPage } from './pages/PlateHistoryPage';
import { ObjectTrackingPage } from './pages/ObjectTrackingPage';
import { ParkingLotManagementPage } from './pages/ParkingLotManagementPage';
import { ParkingSpaceEditorPage } from './pages/ParkingSpaceEditorPage';
import { ProtectedRoute } from './components/ProtectedRoute';
import { useAuth } from './context/AuthContext';

function App() {
  const { user, role, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gradient-to-b from-strawberry-200 via-white to-matcha-200 flex">
        {/* Mobile Overlay */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside className={`${
          sidebarOpen ? 'w-64' : 'w-20'
        } bg-white/95 backdrop-blur shadow-lg border-r border-strawberry-100 transition-all duration-300 flex flex-col fixed h-screen z-50 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}>
          {/* Sidebar Header */}
          <div className="p-4 border-b border-strawberry-100 flex items-center justify-between">
            {sidebarOpen && (
              <h1 className="text-xl font-bold text-strawberry-900">Smart Parking</h1>
            )}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-strawberry-50 text-strawberry-700 flex-shrink-0"
              aria-label="Toggle sidebar"
            >
              {sidebarOpen ? '◀' : '▶'}
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-2">
              {/* 1. Space Detection */}
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                    isActive
                      ? 'bg-strawberry-200 text-strawberry-900 border border-strawberry-400 shadow-inner'
                      : 'bg-white text-strawberry-700 border border-strawberry-100 hover:bg-strawberry-50'
                  }`
                }
              >
                <span className="text-xl flex-shrink-0">🎥</span>
                {sidebarOpen && <span className="truncate">Space Detection</span>}
              </NavLink>

              {/* 2. Detection History */}
              <NavLink
                to="/history"
                className={({ isActive }) =>
                  `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                    isActive
                      ? 'bg-strawberry-200 text-strawberry-900 border border-strawberry-400 shadow-inner'
                      : 'bg-white text-strawberry-700 border border-strawberry-100 hover:bg-strawberry-50'
                  }`
                }
              >
                <span className="text-xl flex-shrink-0">📊</span>
                {sidebarOpen && <span className="truncate">Detection History</span>}
              </NavLink>

              {/* 3. Stats */}
              <NavLink
                to="/stats"
                className={({ isActive }) =>
                  `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                    isActive
                      ? 'bg-strawberry-200 text-strawberry-900 border border-strawberry-400 shadow-inner'
                      : 'bg-white text-strawberry-700 border border-strawberry-100 hover:bg-strawberry-50'
                  }`
                }
              >
                <span className="text-xl flex-shrink-0">📈</span>
                {sidebarOpen && <span className="truncate">Stats</span>}
              </NavLink>

              {/* 4. Alerts */}
              <NavLink
                to="/alerts"
                className={({ isActive }) =>
                  `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                    isActive
                      ? 'bg-danger/10 text-danger-700 border border-danger/40 shadow-inner'
                      : 'bg-strawberry-50 text-danger border border-danger/40 hover:bg-danger/10'
                  }`
                }
              >
                <span className="text-xl flex-shrink-0">🚨</span>
                {sidebarOpen && <span className="truncate">Alerts</span>}
              </NavLink>

              {/* 5. Stream Host */}
              {user && role === 'admin' && (
                <NavLink
                  to="/stream/host"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-strawberry-300 text-strawberry-900 border border-strawberry-500 shadow-inner'
                        : 'bg-white text-strawberry-700 border border-strawberry-100 hover:bg-strawberry-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">📹</span>
                  {sidebarOpen && <span className="truncate">Stream Host</span>}
                </NavLink>
              )}

              {/* 6. Stream View */}
              <NavLink
                to="/stream/view"
                className={({ isActive }) =>
                  `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                    isActive
                      ? 'bg-matcha-200 text-matcha-900 border border-matcha-500 shadow-inner'
                      : 'bg-white text-accent-700 border border-accent-100 hover:bg-accent-50'
                  }`
                }
              >
                <span className="text-xl flex-shrink-0">👀</span>
                {sidebarOpen && <span className="truncate">Stream View</span>}
              </NavLink>

              {/* 7. Plate History */}
              {user && role === 'admin' && (
                <NavLink
                  to="/plate/history"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-matcha-300 text-matcha-950 border border-matcha-600 shadow-inner'
                        : 'bg-white text-matcha-800 border border-matcha-100 hover:bg-matcha-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">📘</span>
                  {sidebarOpen && <span className="truncate">Plate History</span>}
                </NavLink>
              )}

              {/* 8. Multi Stream Host */}
              {user && role === 'admin' && (
                <NavLink
                  to="/stream/host-multi"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-strawberry-400 text-strawberry-950 border border-strawberry-600 shadow-inner'
                        : 'bg-white text-strawberry-800 border border-strawberry-100 hover:bg-strawberry-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">📡</span>
                  {sidebarOpen && <span className="truncate">Multi Stream Host</span>}
                </NavLink>
              )}

              {/* 9. Multi Stream View */}
              {user && (
                <NavLink
                  to="/stream/multi"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-matcha-300 text-matcha-950 border border-matcha-500 shadow-inner'
                        : 'bg-white text-accent-700 border border-accent-100 hover:bg-accent-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">🧩</span>
                  {sidebarOpen && <span className="truncate">Multi Stream View</span>}
                </NavLink>
              )}

              {/* 10. Parking Lot Management */}
              {user && role === 'admin' && (
                <NavLink
                  to="/parking-lots"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-purple-200 text-purple-900 border border-purple-500 shadow-inner'
                        : 'bg-white text-purple-700 border border-purple-100 hover:bg-purple-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">🏢</span>
                  {sidebarOpen && <span className="truncate">Parking Lots</span>}
                </NavLink>
              )}

              {/* 11. Object Tracking */}
              {user && (
                <NavLink
                  to="/tracking"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-matcha-400 text-matcha-950 border border-matcha-600 shadow-inner'
                        : 'bg-white text-matcha-800 border border-matcha-100 hover:bg-matcha-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">🎯</span>
                  {sidebarOpen && <span className="truncate">Object Tracking</span>}
                </NavLink>
              )}

              {/* 11.5. Parking Space Editor */}
              {user && role === 'admin' && (
                <NavLink
                  to="/parking-spaces"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-blue-200 text-blue-900 border border-blue-500 shadow-inner'
                        : 'bg-white text-blue-700 border border-blue-100 hover:bg-blue-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">📐</span>
                  {sidebarOpen && <span className="truncate">Parking Space Editor</span>}
                </NavLink>
              )}

              {/* 12. Account */}
              {user && (
                <NavLink
                  to="/account"
                  className={({ isActive }) =>
                    `flex items-center ${sidebarOpen ? 'gap-3 px-4' : 'justify-center px-2'} py-3 rounded-lg font-medium transition-all ${
                      isActive
                        ? 'bg-strawberry-300 text-strawberry-900 border border-strawberry-500 shadow-inner'
                        : 'bg-white text-strawberry-700 border border-strawberry-100 hover:bg-strawberry-50'
                    }`
                  }
                >
                  <span className="text-xl flex-shrink-0">👤</span>
                  {sidebarOpen && <span className="truncate">Account</span>}
                </NavLink>
              )}
            </nav>

            {/* Sidebar Footer - User Info & Logout */}
            <div className="p-4 border-t border-strawberry-100 space-y-3">
              {user ? (
                <>
                  {sidebarOpen && (
                    <div className="text-sm text-strawberry-800 mb-2 px-2">
                      <p className="font-medium truncate">{user.email}</p>
                      {role && <p className="text-xs text-strawberry-600">({role})</p>}
                    </div>
                  )}
                  <button
                    onClick={logout}
                    className={`w-full ${sidebarOpen ? 'px-4' : 'px-2'} py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-800 transition shadow-sm flex items-center ${sidebarOpen ? 'justify-center gap-2' : 'justify-center'}`}
                  >
                    <span className="flex-shrink-0">🚪</span>
                    {sidebarOpen && <span>Log out</span>}
                  </button>
                </>
              ) : (
                <div className="space-y-2">
                  <NavLink
                    to="/login"
                    className={({ isActive }) =>
                      `flex items-center ${sidebarOpen ? 'justify-center gap-2 px-4' : 'justify-center px-2'} py-2 rounded-lg font-medium transition-all ${
                        isActive
                          ? 'bg-strawberry-200 text-strawberry-900 border border-strawberry-400 shadow-inner'
                          : 'bg-gray-900 text-white hover:bg-gray-800'
                      }`
                    }
                  >
                    <span className="flex-shrink-0">🔐</span>
                    {sidebarOpen && <span>Login</span>}
                  </NavLink>
                  <NavLink
                    to="/register"
                    className={({ isActive }) =>
                      `flex items-center ${sidebarOpen ? 'justify-center gap-2 px-4' : 'justify-center px-2'} py-2 rounded-lg font-medium transition-all ${
                        isActive
                          ? 'bg-matcha-200 text-matcha-900 border border-matcha-500 shadow-inner'
                          : 'bg-accent-500 text-white hover:bg-accent-600'
                      }`
                    }
                  >
                    <span className="flex-shrink-0">➕</span>
                    {sidebarOpen && <span>Register</span>}
                  </NavLink>
                </div>
              )}
            </div>
        </aside>

        {/* Main Content */}
        <main className={`flex-1 transition-all duration-300 ${
          sidebarOpen ? 'lg:ml-64' : 'lg:ml-20'
        }`}>
          {/* Mobile Menu Button */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="fixed top-4 left-4 z-30 p-3 bg-white rounded-lg shadow-lg border border-strawberry-100 hover:bg-strawberry-50 text-strawberry-700 lg:hidden"
              aria-label="Open menu"
            >
              ☰
            </button>
          )}

          {/* Routes */}
          <Routes>
          <Route path="/" element={<SpaceDetectionPage />} />
          <Route 
            path="/history" 
            element={
              <ProtectedRoute roles={['admin']}>
                <HistoryPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/stats" 
            element={
              <ProtectedRoute roles={['admin']}>
                <StatsPage />
              </ProtectedRoute>
            } 
          />
          <Route
            path="/plate/history"
            element={
              <ProtectedRoute roles={['admin']}>
                <PlateHistoryPage />
              </ProtectedRoute>
            }
          />
          <Route 
            path="/alerts" 
            element={
              <ProtectedRoute roles={['admin']}>
                <AlertsPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/cameras" 
            element={
              <ProtectedRoute roles={['admin']}>
                <MultiCameraPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/account" 
            element={
              <ProtectedRoute>
                <AccountPage />
              </ProtectedRoute>
            } 
          />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route 
            path="/stream/host" 
            element={
              <ProtectedRoute roles={['admin']}>
                <StreamHostPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/stream/host-multi" 
            element={
              <ProtectedRoute roles={['admin']}>
                <MultiStreamHostPage />
              </ProtectedRoute>
            } 
          />
          <Route path="/stream/view" element={<StreamViewerPage />} />
          <Route 
            path="/stream/multi" 
            element={
              <ProtectedRoute>
                <MultiStreamViewerPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/tracking" 
            element={
              <ProtectedRoute>
                <ObjectTrackingPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/parking-spaces" 
            element={
              <ProtectedRoute roles={['admin']}>
                <ParkingSpaceEditorPage />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/parking-lots" 
            element={
              <ProtectedRoute roles={['admin']}>
                <ParkingLotManagementPage />
              </ProtectedRoute>
            } 
          />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
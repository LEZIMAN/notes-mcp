import { Routes, Route } from 'react-router-dom'
import './App.css'
import HomePage from './pages/HomePage'
import NoteDetailPage from './pages/NoteDetailPage'
import DashboardPage from './pages/DashboardPage'
import LearningPage from './pages/LearningPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/note/:title" element={<NoteDetailPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/learn" element={<LearningPage />} />
    </Routes>
  )
}

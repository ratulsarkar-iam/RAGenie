import { useState, useEffect, useCallback } from 'react'
import {
  Brain, Search, CheckCircle2, XCircle, Bell, BookOpen,
  Loader2, Send, Sparkles, User, TrendingUp, Clock, RefreshCw
} from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import {
  searchMemories, executeTask, getLearningSummary,
  triggerBriefing, getDueReviews, storeMemory,
  type Memory, type LearningSummary, type TaskResult
} from '../api/assistant'

type Section = 'memory' | 'tasks' | 'learning' | 'proactive'

export default function PersonalAssistant() {
  const { theme } = useTheme()
  const [activeSection, setActiveSection] = useState<Section>('memory')

  // ── Memory state ────────────────────────────────────────────────────────────
  const [memQuery, setMemQuery] = useState('')
  const [memories, setMemories] = useState<Memory[]>([])
  const [memLoading, setMemLoading] = useState(false)
  const [memStore, setMemStore] = useState('')
  const [memType, setMemType] = useState('context')
  const [memStoreStatus, setMemStoreStatus] = useState<string | null>(null)

  // ── Tasks state ─────────────────────────────────────────────────────────────
  const [taskInput, setTaskInput] = useState('')
  const [taskLoading, setTaskLoading] = useState(false)
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null)

  // ── Learning state ──────────────────────────────────────────────────────────
  const [learningSummary, setLearningSummary] = useState<LearningSummary | null>(null)
  const [learningLoading, setLearningLoading] = useState(false)

  // ── Proactive state ─────────────────────────────────────────────────────────
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [briefingStatus, setBriefingStatus] = useState<string | null>(null)
  const [dueReviews, setDueReviews] = useState<any[]>([])
  const [reviewsLoading, setReviewsLoading] = useState(false)

  const card = `backdrop-blur-xl border rounded-xl p-4 ${
    theme === 'dark' ? 'bg-slate-800/60 border-slate-700' : 'bg-white border-gray-200'
  }`

  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm outline-none focus:ring-2 transition-all ${
    theme === 'dark'
      ? 'bg-slate-700 border-slate-600 text-white focus:ring-blue-500 placeholder-slate-400'
      : 'bg-white border-gray-300 text-slate-900 focus:ring-blue-400 placeholder-slate-400'
  }`

  const btnPrimary = `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white transition-all disabled:opacity-50`

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleMemSearch = useCallback(async () => {
    if (!memQuery.trim()) return
    setMemLoading(true)
    try {
      const res = await searchMemories(memQuery)
      setMemories(res.memories)
    } catch {
      setMemories([])
    } finally {
      setMemLoading(false)
    }
  }, [memQuery])

  const handleMemStore = async () => {
    if (!memStore.trim()) return
    setMemStoreStatus('storing')
    try {
      await storeMemory(memStore, memType)
      setMemStore('')
      setMemStoreStatus('stored')
      setTimeout(() => setMemStoreStatus(null), 2500)
    } catch {
      setMemStoreStatus('error')
      setTimeout(() => setMemStoreStatus(null), 2500)
    }
  }

  const handleTask = async () => {
    if (!taskInput.trim()) return
    setTaskLoading(true)
    setTaskResult(null)
    try {
      const res = await executeTask(taskInput)
      setTaskResult(res)
    } catch (e: any) {
      setTaskResult({ success: false, summary: e.message, details: {} })
    } finally {
      setTaskLoading(false)
    }
  }

  const loadLearning = async () => {
    setLearningLoading(true)
    try {
      const res = await getLearningSummary()
      setLearningSummary(res)
    } catch {
      setLearningSummary(null)
    } finally {
      setLearningLoading(false)
    }
  }

  const handleBriefing = async () => {
    setBriefingLoading(true)
    setBriefingStatus(null)
    try {
      const res = await triggerBriefing()
      setBriefingStatus(res.status || 'Briefing delivered!')
    } catch {
      setBriefingStatus('Failed to deliver briefing.')
    } finally {
      setBriefingLoading(false)
    }
  }

  const loadDueReviews = async () => {
    setReviewsLoading(true)
    try {
      const res = await getDueReviews()
      setDueReviews(res.due_reviews || [])
    } catch {
      setDueReviews([])
    } finally {
      setReviewsLoading(false)
    }
  }

  useEffect(() => {
    if (activeSection === 'learning') loadLearning()
    if (activeSection === 'proactive') loadDueReviews()
  }, [activeSection])

  // ── Section nav ─────────────────────────────────────────────────────────────
  const sections: { id: Section; label: string; icon: any }[] = [
    { id: 'memory', label: 'Memory', icon: Brain },
    { id: 'tasks', label: 'Tasks', icon: CheckCircle2 },
    { id: 'learning', label: 'Learning', icon: BookOpen },
    { id: 'proactive', label: 'Proactive', icon: Bell },
  ]

  const label = theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
  const muted = theme === 'dark' ? 'text-slate-400' : 'text-slate-500'

  return (
    <div className={`flex flex-col h-full overflow-hidden ${
      theme === 'dark' ? 'text-white' : 'text-slate-900'
    }`}>
      {/* Section tabs */}
      <div className={`flex gap-1 p-4 border-b ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200'
      }`}>
        {sections.map(({ id, label: lbl, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveSection(id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              activeSection === id
                ? theme === 'dark'
                  ? 'bg-blue-600 text-white'
                  : 'bg-blue-500 text-white'
                : theme === 'dark'
                ? 'text-slate-400 hover:bg-slate-800 hover:text-white'
                : 'text-slate-600 hover:bg-gray-100'
            }`}
          >
            <Icon className="w-4 h-4" />
            {lbl}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── MEMORY ────────────────────────────────────────────────────── */}
        {activeSection === 'memory' && (
          <>
            <div className={card}>
              <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${label}`}>
                <Search className="w-4 h-4" /> Search Memories
              </h3>
              <div className="flex gap-2">
                <input
                  className={inputCls}
                  placeholder="Search stored memories..."
                  value={memQuery}
                  onChange={e => setMemQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleMemSearch()}
                />
                <button className={btnPrimary} onClick={handleMemSearch} disabled={memLoading}>
                  {memLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                </button>
              </div>

              {memories.length > 0 && (
                <div className="mt-3 space-y-2">
                  {memories.map(m => (
                    <div key={m.id} className={`p-3 rounded-lg border text-sm ${
                      theme === 'dark'
                        ? 'bg-slate-700/60 border-slate-600'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          theme === 'dark'
                            ? 'bg-blue-900/50 text-blue-300'
                            : 'bg-blue-100 text-blue-700'
                        }`}>{m.type}</span>
                        <span className={`text-xs ${muted}`}>
                          {new Date(m.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className={`leading-relaxed ${label}`}>{m.content}</p>
                    </div>
                  ))}
                </div>
              )}
              {memories.length === 0 && memQuery && !memLoading && (
                <p className={`text-xs mt-3 ${muted}`}>No memories found for "{memQuery}"</p>
              )}
            </div>

            <div className={card}>
              <h3 className={`text-sm font-semibold mb-3 flex items-center gap-2 ${label}`}>
                <Sparkles className="w-4 h-4" /> Store a Memory
              </h3>
              <div className="flex gap-2 mb-2">
                <select
                  className={`${inputCls} w-auto`}
                  value={memType}
                  onChange={e => setMemType(e.target.value)}
                >
                  <option value="context">Context</option>
                  <option value="preference">Preference</option>
                  <option value="fact">Fact</option>
                  <option value="goal">Goal</option>
                </select>
              </div>
              <textarea
                className={`${inputCls} resize-none`}
                rows={3}
                placeholder="e.g. I prefer concise explanations with code examples"
                value={memStore}
                onChange={e => setMemStore(e.target.value)}
              />
              <div className="flex items-center gap-3 mt-2">
                <button className={btnPrimary} onClick={handleMemStore} disabled={memStoreStatus === 'storing'}>
                  {memStoreStatus === 'storing'
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Send className="w-4 h-4" />}
                  Store
                </button>
                {memStoreStatus === 'stored' && (
                  <span className="text-xs text-green-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Stored!
                  </span>
                )}
                {memStoreStatus === 'error' && (
                  <span className="text-xs text-red-400 flex items-center gap-1">
                    <XCircle className="w-3 h-3" /> Failed
                  </span>
                )}
              </div>
            </div>
          </>
        )}

        {/* ── TASKS ─────────────────────────────────────────────────────── */}
        {activeSection === 'tasks' && (
          <div className={card}>
            <h3 className={`text-sm font-semibold mb-1 flex items-center gap-2 ${label}`}>
              <CheckCircle2 className="w-4 h-4" /> Natural Language Task Execution
            </h3>
            <p className={`text-xs mb-4 ${muted}`}>
              Describe a task in plain English — RAGenie will detect the type and execute it.
            </p>

            <div className="flex gap-2 mb-2">
              <input
                className={inputCls}
                placeholder="e.g. Create a reminder to review the project tomorrow"
                value={taskInput}
                onChange={e => setTaskInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleTask()}
              />
              <button className={btnPrimary} onClick={handleTask} disabled={taskLoading || !taskInput.trim()}>
                {taskLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </div>

            <div className={`flex flex-wrap gap-2 mb-4`}>
              {[
                'Create a reminder to review the project',
                'Schedule a team meeting for Friday',
                'Take a note: follow up with the design team',
              ].map(ex => (
                <button
                  key={ex}
                  onClick={() => setTaskInput(ex)}
                  className={`text-xs px-2 py-1 rounded-lg border transition-all ${
                    theme === 'dark'
                      ? 'border-slate-600 text-slate-400 hover:bg-slate-700'
                      : 'border-gray-300 text-slate-500 hover:bg-gray-100'
                  }`}
                >
                  {ex}
                </button>
              ))}
            </div>

            {taskResult && (
              <div className={`p-4 rounded-lg border mt-2 ${
                taskResult.success
                  ? theme === 'dark'
                    ? 'bg-green-900/20 border-green-700'
                    : 'bg-green-50 border-green-200'
                  : theme === 'dark'
                  ? 'bg-red-900/20 border-red-700'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {taskResult.success
                    ? <CheckCircle2 className="w-4 h-4 text-green-400" />
                    : <XCircle className="w-4 h-4 text-red-400" />}
                  <span className={`text-sm font-medium ${
                    taskResult.success ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {taskResult.success ? 'Task Executed' : 'Task Failed'}
                  </span>
                  {taskResult.task_type && (
                    <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
                      theme === 'dark'
                        ? 'bg-slate-700 text-slate-300'
                        : 'bg-gray-200 text-slate-600'
                    }`}>{taskResult.task_type}</span>
                  )}
                </div>
                <p className={`text-sm ${label}`}>{taskResult.summary}</p>
                {Object.keys(taskResult.details).length > 0 && (
                  <pre className={`mt-2 text-xs p-2 rounded overflow-x-auto ${
                    theme === 'dark' ? 'bg-slate-900 text-slate-300' : 'bg-gray-100 text-slate-700'
                  }`}>
                    {JSON.stringify(taskResult.details, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── LEARNING ──────────────────────────────────────────────────── */}
        {activeSection === 'learning' && (
          <>
            <div className="flex items-center justify-between">
              <h3 className={`text-sm font-semibold flex items-center gap-2 ${label}`}>
                <TrendingUp className="w-4 h-4" /> Learning Progress
              </h3>
              <button
                onClick={loadLearning}
                className={`p-1.5 rounded-lg transition-all ${
                  theme === 'dark' ? 'hover:bg-slate-700' : 'hover:bg-gray-100'
                }`}
                title="Refresh"
              >
                <RefreshCw className={`w-4 h-4 ${learningLoading ? 'animate-spin' : ''} ${muted}`} />
              </button>
            </div>

            {learningLoading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
              </div>
            )}

            {!learningLoading && learningSummary && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className={card}>
                    <p className={`text-xs ${muted}`}>Total Feedback</p>
                    <p className="text-2xl font-bold text-blue-400">
                      {learningSummary.total_feedback ?? 0}
                    </p>
                  </div>
                  <div className={card}>
                    <p className={`text-xs ${muted}`}>Positive Rate</p>
                    <p className={`text-2xl font-bold ${
                      (learningSummary.positive_rate ?? 0) >= 0.7 ? 'text-green-400' : 'text-yellow-400'
                    }`}>
                      {Math.round((learningSummary.positive_rate ?? 0) * 100)}%
                    </p>
                  </div>
                </div>

                {learningSummary.mastery_overview &&
                  Object.keys(learningSummary.mastery_overview).length > 0 && (
                  <div className={card}>
                    <h4 className={`text-xs font-semibold mb-3 ${label}`}>Topic Mastery</h4>
                    <div className="space-y-2">
                      {Object.entries(learningSummary.mastery_overview).map(([topic, score]) => (
                        <div key={topic}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className={muted}>{topic}</span>
                            <span className={label}>{Math.round((score as number) * 100)}%</span>
                          </div>
                          <div className={`h-1.5 rounded-full overflow-hidden ${
                            theme === 'dark' ? 'bg-slate-700' : 'bg-gray-200'
                          }`}>
                            <div
                              className={`h-full rounded-full transition-all ${
                                (score as number) >= 0.7
                                  ? 'bg-green-500'
                                  : (score as number) >= 0.4
                                  ? 'bg-yellow-500'
                                  : 'bg-red-500'
                              }`}
                              style={{ width: `${Math.round((score as number) * 100)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {learningSummary.topics_covered?.length > 0 && (
                  <div className={card}>
                    <h4 className={`text-xs font-semibold mb-2 ${label}`}>Topics Covered</h4>
                    <div className="flex flex-wrap gap-1.5">
                      {learningSummary.topics_covered.map(t => (
                        <span key={t} className={`text-xs px-2 py-0.5 rounded-full ${
                          theme === 'dark'
                            ? 'bg-purple-900/50 text-purple-300 border border-purple-800'
                            : 'bg-purple-100 text-purple-700 border border-purple-200'
                        }`}>{t}</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {!learningLoading && !learningSummary && (
              <div className={`${card} text-center py-8`}>
                <BookOpen className={`w-8 h-8 mx-auto mb-2 ${muted}`} />
                <p className={`text-sm ${muted}`}>No learning data yet.<br />
                  Submit 👍/👎 feedback on chat messages to build your profile.</p>
              </div>
            )}
          </>
        )}

        {/* ── PROACTIVE ─────────────────────────────────────────────────── */}
        {activeSection === 'proactive' && (
          <>
            <div className={card}>
              <h3 className={`text-sm font-semibold mb-1 flex items-center gap-2 ${label}`}>
                <Bell className="w-4 h-4" /> Daily Briefing
              </h3>
              <p className={`text-xs mb-4 ${muted}`}>
                Trigger a proactive briefing based on your learning context and pending tasks.
              </p>
              <button
                className={`${btnPrimary} w-full justify-center`}
                onClick={handleBriefing}
                disabled={briefingLoading}
              >
                {briefingLoading
                  ? <Loader2 className="w-4 h-4 animate-spin" />
                  : <Bell className="w-4 h-4" />}
                {briefingLoading ? 'Generating briefing...' : 'Trigger Briefing'}
              </button>
              {briefingStatus && (
                <p className={`text-xs mt-3 text-center ${
                  briefingStatus.toLowerCase().includes('fail') ? 'text-red-400' : 'text-green-400'
                }`}>
                  {briefingStatus}
                </p>
              )}
            </div>

            <div className={card}>
              <div className="flex items-center justify-between mb-3">
                <h3 className={`text-sm font-semibold flex items-center gap-2 ${label}`}>
                  <Clock className="w-4 h-4" /> Due Reviews
                </h3>
                <button
                  onClick={loadDueReviews}
                  className={`p-1.5 rounded-lg transition-all ${
                    theme === 'dark' ? 'hover:bg-slate-700' : 'hover:bg-gray-100'
                  }`}
                >
                  <RefreshCw className={`w-4 h-4 ${reviewsLoading ? 'animate-spin' : ''} ${muted}`} />
                </button>
              </div>

              {reviewsLoading && (
                <div className="flex justify-center py-4">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
                </div>
              )}

              {!reviewsLoading && dueReviews.length === 0 && (
                <p className={`text-sm text-center py-4 ${muted}`}>
                  No reviews due right now.
                </p>
              )}

              {!reviewsLoading && dueReviews.length > 0 && (
                <div className="space-y-2">
                  {dueReviews.map((r, i) => (
                    <div key={i} className={`p-3 rounded-lg border flex items-center justify-between ${
                      theme === 'dark'
                        ? 'bg-slate-700/60 border-slate-600'
                        : 'bg-gray-50 border-gray-200'
                    }`}>
                      <div>
                        <p className={`text-sm font-medium ${label}`}>{r.topic}</p>
                        <p className={`text-xs ${muted}`}>
                          Mastery: {Math.round((r.mastery ?? 0) * 100)}%
                          {r.days_overdue > 0 && ` · ${r.days_overdue}d overdue`}
                        </p>
                      </div>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                        (r.mastery ?? 0) >= 0.7
                          ? 'bg-green-500/20 text-green-400'
                          : (r.mastery ?? 0) >= 0.4
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-red-500/20 text-red-400'
                      }`}>
                        {Math.round((r.mastery ?? 0) * 100)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className={`${card} border-dashed`}>
              <div className="flex items-center gap-2 mb-2">
                <User className={`w-4 h-4 ${muted}`} />
                <h4 className={`text-xs font-semibold ${label}`}>How Proactive Mode Works</h4>
              </div>
              <ul className={`text-xs space-y-1.5 ${muted}`}>
                <li>• RAGenie monitors your chat patterns and builds a learning profile</li>
                <li>• Spaced repetition schedules review reminders at optimal intervals</li>
                <li>• The briefing synthesises your pending tasks and weak topics</li>
                <li>• 👍/👎 feedback on messages directly updates your mastery scores</li>
              </ul>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

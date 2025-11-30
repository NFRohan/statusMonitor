import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { Activity, Bell, Trash2, Plus, Save, AlertTriangle } from 'lucide-react';
import axios from 'axios';

const Alerts = () => {
    const { user, logout, tokens } = useAuth();
    const [rules, setRules] = useState([]);
    const [agents, setAgents] = useState([]);
    const [recipient, setRecipient] = useState({ telegram_chat_id: '', enabled: true });
    const [loading, setLoading] = useState(true);
    const [newRule, setNewRule] = useState({
        agent_id: '',
        metric_type: 'cpu',
        condition: 'gt',
        threshold: 90
    });
    const [message, setMessage] = useState({ type: '', text: '' });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const headers = { Authorization: `Bearer ${tokens.access_token}` };
            
            const [rulesRes, agentsRes, recipientRes] = await Promise.all([
                axios.get('/api/alerts/rules', { headers }),
                axios.get('http://localhost:8000/agents', { headers }),
                axios.get('/api/alerts/recipient', { headers })
            ]);

            setRules(rulesRes.data);
            setAgents(agentsRes.data);
            if (recipientRes.data) {
                setRecipient(recipientRes.data);
            }
            
            if (agentsRes.data.length > 0) {
                setNewRule(prev => ({ ...prev, agent_id: agentsRes.data[0].token })); // Using token as ID for now based on backend logic? 
                // Wait, backend uses agent_id which is usually the ID from DB, but ingestion uses token to identify.
                // Let's check alert_service logic. It uses agent_id from the metric payload.
                // Ingestion service adds "agent_id" = token_info["agent_id"] (which is DB ID).
                // So we should use agent.id
                setNewRule(prev => ({ ...prev, agent_id: agentsRes.data[0].id.toString() }));
            }
        } catch (err) {
            console.error('Error fetching data:', err);
            setMessage({ type: 'error', text: 'Failed to load data' });
        } finally {
            setLoading(false);
        }
    };

    const handleSaveRecipient = async () => {
        try {
            await axios.post('/api/alerts/recipient', recipient, {
                headers: { Authorization: `Bearer ${tokens.access_token}` }
            });
            setMessage({ type: 'success', text: 'Telegram settings saved' });
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to save Telegram settings' });
        }
    };

    const handleAddRule = async (e) => {
        e.preventDefault();
        try {
            const res = await axios.post('/api/alerts/rules', newRule, {
                headers: { Authorization: `Bearer ${tokens.access_token}` }
            });
            setRules([...rules, res.data]);
            setMessage({ type: 'success', text: 'Alert rule added' });
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to add rule' });
        }
    };

    const handleDeleteRule = async (id) => {
        try {
            await axios.delete(`/api/alerts/rules/${id}`, {
                headers: { Authorization: `Bearer ${tokens.access_token}` }
            });
            setRules(rules.filter(r => r.id !== id));
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to delete rule' });
        }
    };

    const getAgentName = (id) => {
        const agent = agents.find(a => a.id.toString() === id.toString());
        return agent ? agent.name : id;
    };

    if (loading) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between h-16">
                        <div className="flex items-center">
                            <Link to="/agents" className="flex items-center">
                                <Activity className="h-8 w-8 text-indigo-600" />
                                <span className="ml-2 text-xl font-bold text-gray-900">StatusMonitor</span>
                            </Link>
                            <div className="ml-10 flex items-baseline space-x-4">
                                <Link to="/agents" className="text-gray-500 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Agents</Link>
                                <Link to="/alerts" className="text-gray-900 px-3 py-2 rounded-md text-sm font-medium">Alerts</Link>
                            </div>
                        </div>
                        <div className="flex items-center space-x-4">
                            <span className="text-gray-700">Welcome, {user?.username}</span>
                            <button onClick={logout} className="px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900">Logout</button>
                        </div>
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                {message.text && (
                    <div className={`mb-4 p-4 rounded-md ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                        {message.text}
                    </div>
                )}

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                    {/* Telegram Configuration */}
                    <div className="bg-white shadow rounded-lg p-6">
                        <div className="flex items-center mb-4">
                            <Bell className="h-6 w-6 text-indigo-600 mr-2" />
                            <h2 className="text-lg font-medium text-gray-900">Telegram Configuration</h2>
                        </div>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700">Chat ID</label>
                                <input
                                    type="text"
                                    value={recipient.telegram_chat_id || ''}
                                    onChange={(e) => setRecipient({ ...recipient, telegram_chat_id: e.target.value })}
                                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                                    placeholder="123456789"
                                />
                                <p className="mt-1 text-xs text-gray-500">
                                    Start a chat with the bot to get your Chat ID.
                                </p>
                            </div>
                            <div className="flex items-center">
                                <input
                                    type="checkbox"
                                    checked={recipient.enabled}
                                    onChange={(e) => setRecipient({ ...recipient, enabled: e.target.checked })}
                                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                                />
                                <label className="ml-2 block text-sm text-gray-900">Enable Notifications</label>
                            </div>
                            <button
                                onClick={handleSaveRecipient}
                                className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
                            >
                                <Save className="h-4 w-4 mr-2" />
                                Save Settings
                            </button>
                        </div>
                    </div>

                    {/* Add New Rule */}
                    <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
                        <div className="flex items-center mb-4">
                            <Plus className="h-6 w-6 text-indigo-600 mr-2" />
                            <h2 className="text-lg font-medium text-gray-900">Add Alert Rule</h2>
                        </div>
                        <form onSubmit={handleAddRule} className="grid grid-cols-1 gap-4 sm:grid-cols-5 items-end">
                            <div className="sm:col-span-1">
                                <label className="block text-sm font-medium text-gray-700">Agent</label>
                                <select
                                    value={newRule.agent_id}
                                    onChange={(e) => setNewRule({ ...newRule, agent_id: e.target.value })}
                                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                                >
                                    {agents.map(agent => (
                                        <option key={agent.id} value={agent.id}>{agent.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="sm:col-span-1">
                                <label className="block text-sm font-medium text-gray-700">Metric</label>
                                <select
                                    value={newRule.metric_type}
                                    onChange={(e) => setNewRule({ ...newRule, metric_type: e.target.value })}
                                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                                >
                                    <option value="cpu">CPU Usage</option>
                                    <option value="memory">Memory Usage</option>
                                    <option value="disk">Disk Usage</option>
                                </select>
                            </div>
                            <div className="sm:col-span-1">
                                <label className="block text-sm font-medium text-gray-700">Condition</label>
                                <select
                                    value={newRule.condition}
                                    onChange={(e) => setNewRule({ ...newRule, condition: e.target.value })}
                                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                                >
                                    <option value="gt">Greater Than</option>
                                    <option value="lt">Less Than</option>
                                </select>
                            </div>
                            <div className="sm:col-span-1">
                                <label className="block text-sm font-medium text-gray-700">Threshold (%)</label>
                                <input
                                    type="number"
                                    value={newRule.threshold}
                                    onChange={(e) => setNewRule({ ...newRule, threshold: parseFloat(e.target.value) })}
                                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                                />
                            </div>
                            <div className="sm:col-span-1">
                                <button
                                    type="submit"
                                    className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
                                >
                                    <Plus className="h-4 w-4 mr-2" />
                                    Add
                                </button>
                            </div>
                        </form>
                    </div>

                    {/* Rules List */}
                    <div className="bg-white shadow rounded-lg p-6 lg:col-span-3">
                        <div className="flex items-center mb-4">
                            <AlertTriangle className="h-6 w-6 text-indigo-600 mr-2" />
                            <h2 className="text-lg font-medium text-gray-900">Active Rules</h2>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metric</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Condition</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Threshold</th>
                                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {rules.map((rule) => (
                                        <tr key={rule.id}>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                {getAgentName(rule.agent_id)}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 uppercase">
                                                {rule.metric_type}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                {rule.condition === 'gt' ? 'Greater Than' : 'Less Than'}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                {rule.threshold}%
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                                <button
                                                    onClick={() => handleDeleteRule(rule.id)}
                                                    className="text-red-600 hover:text-red-900"
                                                >
                                                    <Trash2 className="h-5 w-5" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    {rules.length === 0 && (
                                        <tr>
                                            <td colSpan="5" className="px-6 py-4 text-center text-sm text-gray-500">
                                                No alert rules defined.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Alerts;

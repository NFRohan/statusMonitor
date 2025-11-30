import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import { Activity, Plus, Trash2, Copy, RefreshCw, Eye, EyeOff, Monitor, Clock } from 'lucide-react';
import axios from 'axios';

const Agents = () => {
    const { user, logout, tokens } = useAuth();
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showNewAgentForm, setShowNewAgentForm] = useState(false);
    const [newAgentName, setNewAgentName] = useState('');
    const [createdAgent, setCreatedAgent] = useState(null);
    const [visibleTokens, setVisibleTokens] = useState({});
    const [error, setError] = useState('');

    const fetchAgents = async () => {
        try {
            const response = await axios.get('http://localhost:8000/agents', {
                headers: { Authorization: `Bearer ${tokens.access_token}` }
            });
            setAgents(response.data);
        } catch (err) {
            console.error('Failed to fetch agents:', err);
            setError('Failed to load agents');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAgents();
    }, [tokens]);

    const createAgent = async (e) => {
        e.preventDefault();
        if (!newAgentName.trim()) return;

        try {
            const response = await axios.post(
                'http://localhost:8000/agents',
                { name: newAgentName },
                { headers: { Authorization: `Bearer ${tokens.access_token}` } }
            );
            setCreatedAgent(response.data);
            setNewAgentName('');
            fetchAgents();
        } catch (err) {
            console.error('Failed to create agent:', err);
            setError('Failed to create agent');
        }
    };

    const deleteAgent = async (agentId) => {
        if (!confirm('Are you sure you want to delete this agent?')) return;

        try {
            await axios.delete(`http://localhost:8000/agents/${agentId}`, {
                headers: { Authorization: `Bearer ${tokens.access_token}` }
            });
            fetchAgents();
        } catch (err) {
            console.error('Failed to delete agent:', err);
            setError('Failed to delete agent');
        }
    };

    const regenerateToken = async (agentId) => {
        if (!confirm('Are you sure you want to regenerate the token? The old token will stop working.')) return;

        try {
            const response = await axios.post(
                `http://localhost:8000/agents/${agentId}/regenerate-token`,
                {},
                { headers: { Authorization: `Bearer ${tokens.access_token}` } }
            );
            setCreatedAgent(response.data);
            fetchAgents();
        } catch (err) {
            console.error('Failed to regenerate token:', err);
            setError('Failed to regenerate token');
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
    };

    const toggleTokenVisibility = (agentId) => {
        setVisibleTokens(prev => ({
            ...prev,
            [agentId]: !prev[agentId]
        }));
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'Never';
        return new Date(dateString).toLocaleString();
    };

    const getStatusColor = (lastSeen) => {
        if (!lastSeen) return 'bg-gray-400';
        const diff = Date.now() - new Date(lastSeen).getTime();
        if (diff < 60000) return 'bg-green-500'; // Less than 1 minute
        if (diff < 300000) return 'bg-yellow-500'; // Less than 5 minutes
        return 'bg-red-500';
    };

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center">Loading agents...</div>;
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between h-16">
                        <div className="flex items-center">
                            <Activity className="h-8 w-8 text-indigo-600" />
                            <span className="ml-2 text-xl font-bold text-gray-900">StatusMonitor</span>
                        </div>
                        <div className="flex items-center space-x-4">
                            <span className="text-gray-700">Welcome, {user?.username}</span>
                            <button
                                onClick={logout}
                                className="px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900"
                            >
                                Logout
                            </button>
                        </div>
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center mb-6">
                    <h1 className="text-2xl font-bold text-gray-900">My Agents</h1>
                    <button
                        onClick={() => setShowNewAgentForm(true)}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                    >
                        <Plus className="h-4 w-4 mr-2" />
                        New Agent
                    </button>
                </div>

                {error && (
                    <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                        {error}
                        <button onClick={() => setError('')} className="ml-2 font-bold">×</button>
                    </div>
                )}

                {/* New Agent Form Modal */}
                {showNewAgentForm && (
                    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
                        <div className="bg-white rounded-lg p-6 w-full max-w-md">
                            <h2 className="text-lg font-bold mb-4">Create New Agent</h2>
                            <form onSubmit={createAgent}>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        Agent Name
                                    </label>
                                    <input
                                        type="text"
                                        value={newAgentName}
                                        onChange={(e) => setNewAgentName(e.target.value)}
                                        placeholder="e.g., My Desktop, Work Laptop"
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                        required
                                    />
                                </div>
                                <div className="flex justify-end space-x-2">
                                    <button
                                        type="button"
                                        onClick={() => setShowNewAgentForm(false)}
                                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
                                    >
                                        Create
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}

                {/* Created Agent Token Display */}
                {createdAgent && (
                    <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
                        <h3 className="font-bold text-green-800 mb-2">
                            Agent "{createdAgent.name}" Token
                        </h3>
                        <p className="text-sm text-green-700 mb-2">
                            Copy this token and use it to configure your agent. This is the only time you'll see the full token.
                        </p>
                        <div className="flex items-center space-x-2">
                            <code className="flex-1 p-2 bg-white border rounded text-sm font-mono break-all">
                                {createdAgent.token}
                            </code>
                            <button
                                onClick={() => copyToClipboard(createdAgent.token)}
                                className="p-2 text-green-600 hover:text-green-800"
                                title="Copy to clipboard"
                            >
                                <Copy className="h-5 w-5" />
                            </button>
                        </div>
                        <button
                            onClick={() => setCreatedAgent(null)}
                            className="mt-2 text-sm text-green-600 hover:text-green-800"
                        >
                            Dismiss
                        </button>
                    </div>
                )}

                {/* Agents List */}
                {agents.length === 0 ? (
                    <div className="text-center py-12 bg-white rounded-lg shadow">
                        <Monitor className="mx-auto h-12 w-12 text-gray-400" />
                        <h3 className="mt-2 text-sm font-medium text-gray-900">No agents</h3>
                        <p className="mt-1 text-sm text-gray-500">
                            Get started by creating a new agent.
                        </p>
                    </div>
                ) : (
                    <div className="bg-white shadow overflow-hidden rounded-lg">
                        <ul className="divide-y divide-gray-200">
                            {agents.map((agent) => (
                                <li key={agent.id} className="p-4 hover:bg-gray-50">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center space-x-4">
                                            <div className={`h-3 w-3 rounded-full ${getStatusColor(agent.last_seen)}`} />
                                            <div>
                                                <Link
                                                    to={`/agents/${agent.id}`}
                                                    className="text-lg font-medium text-indigo-600 hover:text-indigo-800"
                                                >
                                                    {agent.name}
                                                </Link>
                                                <div className="flex items-center text-sm text-gray-500 mt-1">
                                                    <Clock className="h-4 w-4 mr-1" />
                                                    Last seen: {formatDate(agent.last_seen)}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <Link
                                                to={`/agents/${agent.id}`}
                                                className="p-2 text-gray-400 hover:text-indigo-600"
                                                title="View Dashboard"
                                            >
                                                <Activity className="h-5 w-5" />
                                            </Link>
                                            <button
                                                onClick={() => regenerateToken(agent.id)}
                                                className="p-2 text-gray-400 hover:text-yellow-600"
                                                title="Regenerate Token"
                                            >
                                                <RefreshCw className="h-5 w-5" />
                                            </button>
                                            <button
                                                onClick={() => deleteAgent(agent.id)}
                                                className="p-2 text-gray-400 hover:text-red-600"
                                                title="Delete Agent"
                                            >
                                                <Trash2 className="h-5 w-5" />
                                            </button>
                                        </div>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </main>
        </div>
    );
};

export default Agents;

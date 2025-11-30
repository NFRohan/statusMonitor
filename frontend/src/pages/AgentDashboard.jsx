import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ArrowLeft, Activity, HardDrive, Cpu, Network, Clock } from 'lucide-react';
import axios from 'axios';

const AgentDashboard = () => {
    const { user, tokens } = useAuth();
    const { agentId } = useParams();
    const [agent, setAgent] = useState(null);
    const [metrics, setMetrics] = useState(null);
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [connected, setConnected] = useState(false);

    // Fetch agent details
    useEffect(() => {
        const fetchAgent = async () => {
            try {
                const response = await axios.get(`http://localhost:8000/agents/${agentId}`, {
                    headers: { Authorization: `Bearer ${tokens.access_token}` }
                });
                setAgent(response.data);
            } catch (err) {
                console.error('Failed to fetch agent:', err);
                setError('Failed to load agent details');
            } finally {
                setLoading(false);
            }
        };
        fetchAgent();
    }, [agentId, tokens]);

    // WebSocket connection for real-time metrics
    useEffect(() => {
        if (!user) return;

        const ws = new WebSocket(`ws://localhost:8002/ws?user_id=${user.id}&agent_id=${agentId}`);

        ws.onopen = () => {
            console.log('WebSocket connected');
            setConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                // Only process if it matches our agent
                if (data.agent_id === parseInt(agentId)) {
                    setMetrics(data);
                    setHistory(prev => {
                        const flatData = {
                            time: new Date(data.timestamp * 1000).toLocaleTimeString(),
                            cpuUsage: data.cpu?.usage_percent || 0,
                            memoryUsage: data.memory?.used_percent || 0,
                        };
                        const newHistory = [...prev, flatData];
                        return newHistory.slice(-30);
                    });
                }
            } catch (e) {
                console.error("Error parsing WS message", e);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            setConnected(false);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            setConnected(false);
        };

        return () => {
            ws.close();
        };
    }, [user, agentId]);

    const formatBytes = (bytes) => {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <p className="text-red-600 mb-4">{error}</p>
                    <Link to="/agents" className="text-indigo-600 hover:text-indigo-800">
                        Back to Agents
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between h-16">
                        <div className="flex items-center">
                            <Link to="/agents" className="mr-4 text-gray-500 hover:text-gray-700">
                                <ArrowLeft className="h-6 w-6" />
                            </Link>
                            <Activity className="h-8 w-8 text-indigo-600" />
                            <span className="ml-2 text-xl font-bold text-gray-900">
                                {agent?.name || 'Agent Dashboard'}
                            </span>
                            <span className={`ml-3 px-2 py-1 text-xs rounded-full ${
                                connected ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                                {connected ? 'Live' : 'Disconnected'}
                            </span>
                        </div>
                        <div className="flex items-center">
                            <span className="text-gray-700">Welcome, {user?.username}</span>
                        </div>
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                {!metrics ? (
                    <div className="text-center py-12 bg-white rounded-lg shadow">
                        <Clock className="mx-auto h-12 w-12 text-gray-400 animate-pulse" />
                        <h3 className="mt-2 text-sm font-medium text-gray-900">Waiting for metrics...</h3>
                        <p className="mt-1 text-sm text-gray-500">
                            Make sure the agent is running and connected.
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Summary Cards */}
                        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
                            <div className="bg-white overflow-hidden shadow rounded-lg">
                                <div className="p-5">
                                    <div className="flex items-center">
                                        <div className="flex-shrink-0">
                                            <Cpu className="h-6 w-6 text-gray-400" />
                                        </div>
                                        <div className="ml-5 w-0 flex-1">
                                            <dl>
                                                <dt className="text-sm font-medium text-gray-500 truncate">CPU Usage</dt>
                                                <dd className="text-lg font-medium text-gray-900">
                                                    {metrics.cpu?.usage_percent?.toFixed(1) || 0}%
                                                </dd>
                                            </dl>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-white overflow-hidden shadow rounded-lg">
                                <div className="p-5">
                                    <div className="flex items-center">
                                        <div className="flex-shrink-0">
                                            <Activity className="h-6 w-6 text-gray-400" />
                                        </div>
                                        <div className="ml-5 w-0 flex-1">
                                            <dl>
                                                <dt className="text-sm font-medium text-gray-500 truncate">Memory Usage</dt>
                                                <dd className="text-lg font-medium text-gray-900">
                                                    {metrics.memory?.used_percent?.toFixed(1) || 0}%
                                                </dd>
                                            </dl>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-white overflow-hidden shadow rounded-lg">
                                <div className="p-5">
                                    <div className="flex items-center">
                                        <div className="flex-shrink-0">
                                            <HardDrive className="h-6 w-6 text-gray-400" />
                                        </div>
                                        <div className="ml-5 w-0 flex-1">
                                            <dl>
                                                <dt className="text-sm font-medium text-gray-500 truncate">Disk Usage</dt>
                                                <dd className="text-lg font-medium text-gray-900">
                                                    {metrics.disk?.partitions?.[0]?.percent?.toFixed(1) || 0}%
                                                </dd>
                                            </dl>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="bg-white overflow-hidden shadow rounded-lg">
                                <div className="p-5">
                                    <div className="flex items-center">
                                        <div className="flex-shrink-0">
                                            <Network className="h-6 w-6 text-gray-400" />
                                        </div>
                                        <div className="ml-5 w-0 flex-1">
                                            <dl>
                                                <dt className="text-sm font-medium text-gray-500 truncate">Network Sent</dt>
                                                <dd className="text-lg font-medium text-gray-900">
                                                    {formatBytes(metrics.network?.bytes_sent)}
                                                </dd>
                                            </dl>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Charts */}
                        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                            <div className="bg-white shadow rounded-lg p-6">
                                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">CPU History</h3>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={history}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis 
                                                dataKey="time" 
                                                tick={{ fontSize: 11 }}
                                                interval="preserveStartEnd"
                                            />
                                            <YAxis 
                                                domain={[0, 100]} 
                                                tickFormatter={(value) => `${value}%`}
                                            />
                                            <Tooltip formatter={(value) => [`${value.toFixed(1)}%`, 'CPU']} />
                                            <Legend />
                                            <Line 
                                                type="monotone" 
                                                dataKey="cpuUsage" 
                                                stroke="#8884d8" 
                                                name="CPU %" 
                                                dot={false}
                                                isAnimationActive={false}
                                                strokeWidth={2}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="bg-white shadow rounded-lg p-6">
                                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Memory History</h3>
                                <div className="h-64">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={history}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis 
                                                dataKey="time" 
                                                tick={{ fontSize: 11 }}
                                                interval="preserveStartEnd"
                                            />
                                            <YAxis 
                                                domain={[0, 100]} 
                                                tickFormatter={(value) => `${value}%`}
                                            />
                                            <Tooltip formatter={(value) => [`${value.toFixed(1)}%`, 'Memory']} />
                                            <Legend />
                                            <Line 
                                                type="monotone" 
                                                dataKey="memoryUsage" 
                                                stroke="#82ca9d" 
                                                name="Mem %" 
                                                dot={false}
                                                isAnimationActive={false}
                                                strokeWidth={2}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>

                        {/* System Details */}
                        <div className="mt-6 bg-white shadow rounded-lg p-6">
                            <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">System Details</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <h4 className="font-medium text-gray-700 mb-2">Memory</h4>
                                    <div className="text-sm text-gray-600">
                                        <p>Total: {formatBytes(metrics.memory?.total)}</p>
                                        <p>Available: {formatBytes(metrics.memory?.available)}</p>
                                    </div>
                                </div>
                                <div>
                                    <h4 className="font-medium text-gray-700 mb-2">Network</h4>
                                    <div className="text-sm text-gray-600">
                                        <p>Bytes Sent: {formatBytes(metrics.network?.bytes_sent)}</p>
                                        <p>Bytes Received: {formatBytes(metrics.network?.bytes_recv)}</p>
                                    </div>
                                </div>
                                {metrics.disk?.partitions?.map((partition, idx) => (
                                    <div key={idx}>
                                        <h4 className="font-medium text-gray-700 mb-2">
                                            Disk: {partition.mountpoint}
                                        </h4>
                                        <div className="text-sm text-gray-600">
                                            <p>Total: {formatBytes(partition.total)}</p>
                                            <p>Used: {formatBytes(partition.used)} ({partition.percent}%)</p>
                                            <p>Free: {formatBytes(partition.free)}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
};

export default AgentDashboard;

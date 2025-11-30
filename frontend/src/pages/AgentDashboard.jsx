import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { ArrowLeft, Activity, HardDrive, Cpu, Network, Clock, History, TrendingUp } from 'lucide-react';
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
    
    // Historical data state
    const [historicalCpu, setHistoricalCpu] = useState([]);
    const [historicalMemory, setHistoricalMemory] = useState([]);
    const [historicalTimeRange, setHistoricalTimeRange] = useState('-5m');
    const [historicalLoading, setHistoricalLoading] = useState(false);
    const [summary, setSummary] = useState(null);
    const [activeTab, setActiveTab] = useState('realtime'); // 'realtime' or 'historical'

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

    // Fetch historical data
    const fetchHistoricalData = async (timeRange) => {
        setHistoricalLoading(true);
        try {
            // Set appropriate aggregation interval based on time range
            const intervalMap = {
                '-5m': '10s',
                '-30m': '30s',
                '-1h': '1m',
                '-24h': '5m',
                '-7d': '30m'
            };
            const interval = intervalMap[timeRange] || '1m';
            
            const [cpuRes, memRes, summaryRes] = await Promise.all([
                axios.get(`/api/history/${agentId}/cpu?start=${timeRange}&interval=${interval}`),
                axios.get(`/api/history/${agentId}/memory?start=${timeRange}&interval=${interval}`),
                axios.get(`/api/history/${agentId}/summary?start=${timeRange}`)
            ]);
            
            setHistoricalCpu(cpuRes.data.data.map(d => ({
                time: new Date(d.time).toLocaleString(),
                value: d.value
            })));
            
            setHistoricalMemory(memRes.data.data.map(d => ({
                time: new Date(d.time).toLocaleString(),
                value: d.value
            })));
            
            setSummary(summaryRes.data);
        } catch (err) {
            console.error('Failed to fetch historical data:', err);
        } finally {
            setHistoricalLoading(false);
        }
    };

    useEffect(() => {
        if (activeTab === 'historical') {
            fetchHistoricalData(historicalTimeRange);
        }
    }, [activeTab, historicalTimeRange, agentId]);

    // WebSocket connection for real-time metrics
    useEffect(() => {
        if (!user) return;

        // Use relative WebSocket URL through nginx proxy
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws?user_id=${user.id}&agent_id=${agentId}`;
        console.log('Connecting to WebSocket:', wsUrl);
        const ws = new WebSocket(wsUrl);

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
                        const now = Date.now();
                        const thirtySecondsAgo = now - 30000;
                        const flatData = {
                            time: new Date(data.timestamp * 1000).toLocaleTimeString(),
                            timestamp: data.timestamp * 1000,
                            cpuUsage: data.cpu?.usage_percent || 0,
                            memoryUsage: data.memory?.used_percent || 0,
                        };
                        // Add new data and filter to keep only last 30 seconds
                        const newHistory = [...prev, flatData].filter(
                            item => item.timestamp >= thirtySecondsAgo
                        );
                        return newHistory;
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
                {/* Tabs */}
                <div className="mb-6 border-b border-gray-200">
                    <nav className="-mb-px flex space-x-8">
                        <button
                            onClick={() => setActiveTab('realtime')}
                            className={`py-2 px-1 border-b-2 font-medium text-sm ${
                                activeTab === 'realtime'
                                    ? 'border-indigo-500 text-indigo-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            }`}
                        >
                            <Activity className="inline h-4 w-4 mr-2" />
                            Real-time
                        </button>
                        <button
                            onClick={() => setActiveTab('historical')}
                            className={`py-2 px-1 border-b-2 font-medium text-sm ${
                                activeTab === 'historical'
                                    ? 'border-indigo-500 text-indigo-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            }`}
                        >
                            <History className="inline h-4 w-4 mr-2" />
                            Historical
                        </button>
                    </nav>
                </div>

                {activeTab === 'realtime' && (
                    <>
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
                                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">CPU History (Last 30s)</h3>
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
                                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Memory History (Last 30s)</h3>
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
                    </>
                )}

                {activeTab === 'historical' && (
                <>
                    {/* Time Range Selector */}
                    <div className="mb-6 flex items-center space-x-4">
                        <span className="text-sm font-medium text-gray-700">Time Range:</span>
                        <div className="flex space-x-2 flex-wrap gap-1">
                            {[
                                { value: '-5m', label: '5 Min' },
                                { value: '-30m', label: '30 Min' },
                                { value: '-1h', label: '1 Hour' },
                                { value: '-24h', label: '24 Hours' },
                                { value: '-7d', label: '7 Days' },
                            ].map(({ value, label }) => (
                                <button
                                    key={value}
                                    onClick={() => setHistoricalTimeRange(value)}
                                    className={`px-3 py-1 text-sm rounded-md ${
                                        historicalTimeRange === value
                                            ? 'bg-indigo-600 text-white'
                                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                                    }`}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                        <button
                            onClick={() => fetchHistoricalData(historicalTimeRange)}
                            className="ml-auto px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
                        >
                            Refresh
                        </button>
                    </div>

                    {historicalLoading ? (
                        <div className="text-center py-12 bg-white rounded-lg shadow">
                            <Clock className="mx-auto h-12 w-12 text-gray-400 animate-spin" />
                            <h3 className="mt-2 text-sm font-medium text-gray-900">Loading historical data...</h3>
                        </div>
                    ) : (
                        <>
                            {/* Summary Cards */}
                            {summary && (
                                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4 mb-8">
                                    <div className="bg-white overflow-hidden shadow rounded-lg">
                                        <div className="p-5">
                                            <div className="flex items-center">
                                                <Cpu className="h-6 w-6 text-indigo-500" />
                                                <div className="ml-5">
                                                    <p className="text-sm font-medium text-gray-500">Avg CPU</p>
                                                    <p className="text-2xl font-semibold text-gray-900">
                                                        {summary.cpu.avg.toFixed(1)}%
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="bg-white overflow-hidden shadow rounded-lg">
                                        <div className="p-5">
                                            <div className="flex items-center">
                                                <TrendingUp className="h-6 w-6 text-red-500" />
                                                <div className="ml-5">
                                                    <p className="text-sm font-medium text-gray-500">Peak CPU</p>
                                                    <p className="text-2xl font-semibold text-gray-900">
                                                        {summary.cpu.max.toFixed(1)}%
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="bg-white overflow-hidden shadow rounded-lg">
                                        <div className="p-5">
                                            <div className="flex items-center">
                                                <Activity className="h-6 w-6 text-green-500" />
                                                <div className="ml-5">
                                                    <p className="text-sm font-medium text-gray-500">Avg Memory</p>
                                                    <p className="text-2xl font-semibold text-gray-900">
                                                        {summary.memory.avg.toFixed(1)}%
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="bg-white overflow-hidden shadow rounded-lg">
                                        <div className="p-5">
                                            <div className="flex items-center">
                                                <TrendingUp className="h-6 w-6 text-orange-500" />
                                                <div className="ml-5">
                                                    <p className="text-sm font-medium text-gray-500">Peak Memory</p>
                                                    <p className="text-2xl font-semibold text-gray-900">
                                                        {summary.memory.max.toFixed(1)}%
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Historical Charts */}
                            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                                <div className="bg-white shadow rounded-lg p-6">
                                    <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                                        CPU Usage History
                                    </h3>
                                    <div className="h-72">
                                        {historicalCpu.length > 0 ? (
                                            <ResponsiveContainer width="100%" height="100%">
                                                <AreaChart data={historicalCpu}>
                                                    <CartesianGrid strokeDasharray="3 3" />
                                                    <XAxis 
                                                        dataKey="time" 
                                                        tick={{ fontSize: 10 }}
                                                        interval="preserveStartEnd"
                                                        angle={-45}
                                                        textAnchor="end"
                                                        height={60}
                                                    />
                                                    <YAxis 
                                                        domain={[0, 100]} 
                                                        tickFormatter={(value) => `${value}%`}
                                                    />
                                                    <Tooltip formatter={(value) => [`${value.toFixed(1)}%`, 'CPU']} />
                                                    <Area 
                                                        type="monotone" 
                                                        dataKey="value" 
                                                        stroke="#8884d8" 
                                                        fill="#8884d8"
                                                        fillOpacity={0.3}
                                                        name="CPU %" 
                                                    />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        ) : (
                                            <div className="h-full flex items-center justify-center text-gray-500">
                                                No historical data available
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div className="bg-white shadow rounded-lg p-6">
                                    <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                                        Memory Usage History
                                    </h3>
                                    <div className="h-72">
                                        {historicalMemory.length > 0 ? (
                                            <ResponsiveContainer width="100%" height="100%">
                                                <AreaChart data={historicalMemory}>
                                                    <CartesianGrid strokeDasharray="3 3" />
                                                    <XAxis 
                                                        dataKey="time" 
                                                        tick={{ fontSize: 10 }}
                                                        interval="preserveStartEnd"
                                                        angle={-45}
                                                        textAnchor="end"
                                                        height={60}
                                                    />
                                                    <YAxis 
                                                        domain={[0, 100]} 
                                                        tickFormatter={(value) => `${value}%`}
                                                    />
                                                    <Tooltip formatter={(value) => [`${value.toFixed(1)}%`, 'Memory']} />
                                                    <Area 
                                                        type="monotone" 
                                                        dataKey="value" 
                                                        stroke="#82ca9d" 
                                                        fill="#82ca9d"
                                                        fillOpacity={0.3}
                                                        name="Mem %" 
                                                    />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        ) : (
                                            <div className="h-full flex items-center justify-center text-gray-500">
                                                No historical data available
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Data Points Info */}
                            {summary && (
                                <div className="mt-4 text-center text-sm text-gray-500">
                                    Based on {summary.cpu.data_points} data points
                                </div>
                            )}
                        </>
                    )}
                </>
            )}
            </main>
        </div>
    );
};

export default AgentDashboard;

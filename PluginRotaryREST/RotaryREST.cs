using Common;
using System;
using System.Threading.Tasks;

namespace PluginRotaryREST
{
    class RotaryREST
    {
        private TurntableRestClient _restClient;
        private bool _isConnected = false;
        private int _currentAngle = 0;
        private int _currentTilt = 0;

        static public int nMotors { get { return 2; } }

        public int[] currentSteps
        {
            get
            {
                Report.Info("RotaryREST::currentSteps::get");
                return new int[] { _currentAngle, _currentTilt };
            }
        }

        public string serverUrl
        {
            get
            {
                Report.Info("RotaryREST::serverUrl::get");
                return Properties.Settings.Default.Rotary_REST_ServerUrl;
            }
        }

        public bool IsConnected()
        {
            Report.Info("RotaryREST::IsConnected");
            if (_restClient == null)
            {
                string url = serverUrl;
                Report.Info($"RotaryREST::IsConnected - Creating new TurntableRestClient with URL: {url}");
                _restClient = new TurntableRestClient(url);
            }

            if (!_isConnected)
            {
                try
                {
                    Report.Info("RotaryREST::IsConnected - Checking connection status...");
                    var status = Task.Run(() => _restClient.GetStatus()).Result;

                    if (status != null)
                    {
                        Report.Info($"RotaryREST::IsConnected - Received status: Connected={status.Connected}, Angle={status.Angle}, Tilt={status.Tilt}");
                        _isConnected = status.Connected;
                        _currentAngle = status.Angle;
                        _currentTilt = status.Tilt;
                    }
                    else
                    {
                        Report.Warning("RotaryREST::IsConnected - Status response was null.");
                        _isConnected = false;
                    }
                }
                catch (Exception ex)
                {
                    Report.Warning($"RotaryREST::IsConnected - Exception: {ex.Message}");
                    _isConnected = false;
                }
            }
            Report.Info($"RotaryREST::IsConnected - Returning: {_isConnected}");
            return _isConnected;
        }

        public void Stop()
        {
            Report.Info("RotaryREST::Stop");
            if (!IsConnected())
            {
                Report.Warning("RotaryREST::Stop - Not connected, cannot stop.");
                return;
            }
            try
            {
                Task.Run(() => _restClient.Reset()).Wait();
            }
            catch (Exception ex)
            {
                Report.Warning($"RotaryREST::Stop - Exception: {ex.Message}");
            }
        }

        public bool Move(int motor, int steps)
        {
            Report.Info($"RotaryREST::Move - Motor: {motor}, Steps: {steps}");
            if (!IsConnected())
            {
                Report.Warning("RotaryREST::Move - Not connected, cannot move.");
                return false;
            }

            try
            {
                if (motor == 1) // Rotation
                {
                    int newAngle = _currentAngle + steps;
                    Report.Info($"RotaryREST::Move - Rotating to angle: {newAngle}");
                    Task.Run(() => _restClient.SetPosition(null, newAngle)).Wait();
                    _currentAngle = newAngle;
                }
                else if (motor == 2) // Tilt
                {
                    int requestedTilt = _currentTilt + steps;
                    // Clamping disabled - using requested value directly
                    // int newTilt = Math.Max(-30, Math.Min(30, requestedTilt)); // Clamp to [-30, 30]
                    int newTilt = requestedTilt; // Use requested value without clamping
                    // if (requestedTilt != newTilt)
                    // {
                    //     Report.Warning($"RotaryREST::Move - Tilt requested: {requestedTilt}°, clamped to: {newTilt}° (tilt range is [-30, 30])");
                    // }
                    Report.Info($"RotaryREST::Move - Tilting to: {newTilt}° (requested: {requestedTilt}°, current: {_currentTilt}°)");
                    Task.Run(() => _restClient.SetPosition(newTilt, null)).Wait();
                    _currentTilt = newTilt;
                }
                else
                {
                    Report.Warning($"RotaryREST::Move - Invalid motor number: {motor}");
                    return false;
                }

                return true;
            }
            catch (Exception ex)
            {
                Report.Warning($"RotaryREST::Move - Exception: {ex.Message}");
                return false;
            }
        }
    }
}

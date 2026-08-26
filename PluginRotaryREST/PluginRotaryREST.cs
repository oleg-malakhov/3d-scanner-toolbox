using System;
using System.Collections.Generic;
using System.Configuration;
using Common;
using PluginRotaryInterface;

namespace PluginRotaryREST
{
    public class PluginRotaryREST : PluginRotary
    {
        private Dictionary<string, RotaryREST> rotaries = new Dictionary<string, RotaryREST>();

        public override ApplicationSettingsBase settings { get { return Properties.Settings.Default; } }

        public override string pluginID { get { return "PluginRotaryREST"; } }

        private bool IsLoggingEnabled
        {
            get { return !Properties.Settings.Default.Rotary_REST_DisableLogging; }
        }

        public override List<string> rotaryIDs
        {
            get
            {
                if (IsLoggingEnabled) Report.Info("PluginRotaryREST::rotaryIDs::get");
                List<string> idList = new List<string>();
                string ID = pluginID + "::Turntable";
                RotaryREST rotary = GetRotary(ID);
                if (rotary != null && rotary.IsConnected())
                {
                    idList.Add(ID);
                }
                if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::rotaryIDs - Found {idList.Count} rotary IDs.");
                return idList;
            }
        }

        private RotaryREST GetRotary(string ID)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetRotary - ID: {ID}");
            if (string.IsNullOrWhiteSpace(ID)) return null;

            if (!rotaries.ContainsKey(ID))
            {
                if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetRotary - Creating new RotaryREST for ID: {ID}");
                RotaryREST rotary = new RotaryREST();
                rotaries.Add(ID, rotary);
            }

            return rotaries[ID];
        }

        public override bool IsConnected(string ID)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::IsConnected - ID: {ID}");
            RotaryREST rotary = GetRotary(ID);
            if (rotary == null)
            {
                if (IsLoggingEnabled) Report.Warning($"PluginRotaryREST::IsConnected - No rotary found for ID: {ID}");
                return false;
            }
            bool connected = rotary.IsConnected();
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::IsConnected - Result: {connected}");
            return connected;
        }

        public override bool GetNumMotors(string ID, out int motors)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetNumMotors - ID: {ID}");
            motors = RotaryREST.nMotors;
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetNumMotors - Result: {motors}");
            return true;
        }

        public override bool GetCurrStep(string ID, int motor, out int step)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetCurrStep - ID: {ID}, Motor: {motor}");
            step = 0;
            RotaryREST rotary = GetRotary(ID);
            if (rotary == null) return false;
            if (motor < 1 || motor > RotaryREST.nMotors)
            {
                if (IsLoggingEnabled) Report.Warning($"PluginRotaryREST::GetCurrStep - Invalid motor: {motor}");
                return false;
            }
            step = rotary.currentSteps[motor - 1];
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetCurrStep - Result: {step}");
            return true;
        }

        public override bool GetStepsPerTurn(string ID, int motor, out int steps)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetStepsPerTurn - ID: {ID}, Motor: {motor}");
            steps = 360;
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::GetStepsPerTurn - Result: {steps}");
            return true;
        }

        public override bool SetStepsPerTurn(string ID, int motor, int steps)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::SetStepsPerTurn - ID: {ID}, Motor: {motor}, Steps: {steps}");
            return true;
        }

        public override bool GetMaxSpeed(string ID, int motor, out double speed)
        {
            if (IsLoggingEnabled) Report.Info("PluginRotaryREST::GetMaxSpeed");
            speed = 0;
            return false;
        }

        public override bool SetMaxSpeed(string ID, int motor, double speed)
        {
            if (IsLoggingEnabled) Report.Info("PluginRotaryREST::SetMaxSpeed");
            return false;
        }

        public override bool Move(string ID, int motor, int steps)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Move - ID: {ID}, Motor: {motor}, Steps: {steps}");
            RotaryREST rotary = GetRotary(ID);
            if (rotary == null)
            {
                if (IsLoggingEnabled) Report.Warning($"PluginRotaryREST::Move - No rotary found for ID: {ID}");
                return false;
            }
            bool result = rotary.Move(motor, steps);
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Move - Result: {result}");
            return result;
        }

        public override void Stop()
        {
            if (IsLoggingEnabled) Report.Info("PluginRotaryREST::Stop - Stopping all rotaries.");
            foreach (RotaryREST rotary in rotaries.Values)
            {
                rotary.Stop();
            }
        }

        public override bool Rotate(string ID, int motor, double degrees)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Rotate - Custom override entered. ID: {ID}, Motor: {motor}, Degrees: {degrees}");

            int stepsPerTurn;
            if (IsLoggingEnabled) Report.Info("PluginRotaryREST::Rotate - Calling GetStepsPerTurn...");
            bool success = this.GetStepsPerTurn(ID, motor, out stepsPerTurn);
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Rotate - GetStepsPerTurn returned {success} with stepsPerTurn = {stepsPerTurn}");

            if (!success || stepsPerTurn <= 0)
            {
                if (IsLoggingEnabled) Report.Warning($"PluginRotaryREST::Rotate - Condition failed: !success ({!success}) || stepsPerTurn <= 0 ({stepsPerTurn <= 0}). Aborting rotation.");
                return false;
            }

            // Convert degrees to steps using the standard formula: steps = (degrees / 360.0) * stepsPerTurn
            // For stepsPerTurn = 360, this simplifies to: steps = degrees
            // But we use the formula to be consistent with the base class behavior
            int stepsToMove = (int)(degrees / 360.0 * stepsPerTurn);
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Rotate - Calculated steps to move: {stepsToMove} (from {degrees} degrees with {stepsPerTurn} stepsPerTurn)");

            if (IsLoggingEnabled) Report.Info("PluginRotaryREST::Rotate - Calling Move...");
            bool moveResult = this.Move(ID, motor, stepsToMove);
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Rotate - Move returned {moveResult}.");

            return moveResult;
        }

        public override bool Reset(string ID)
        {
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Reset - ID: {ID}");
            bool result = base.Reset(ID);
            if (IsLoggingEnabled) Report.Info($"PluginRotaryREST::Reset - Result: {result}");
            return result;
        }
    }
}

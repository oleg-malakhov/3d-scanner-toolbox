using Common;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;

namespace PluginRotaryREST
{
    public class TurntableRestClient
    {
        private readonly HttpClient _client;
        private readonly string _baseUrl;

        public TurntableRestClient(string baseUrl)
        {
            Report.Info("TurntableRestClient::TurntableRestClient");
            _client = new HttpClient();
            _baseUrl = baseUrl;
        }

        public async Task<StatusResponse> GetStatus()
        {
            Report.Info("TurntableRestClient::GetStatus");
            var response = await _client.GetAsync($"{_baseUrl}/status").ConfigureAwait(false);
            
            if (response.StatusCode != System.Net.HttpStatusCode.OK)
            {
                var errorContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                string errorMessage = $"TurntableRestClient::GetStatus - Server returned status code {(int)response.StatusCode} ({response.StatusCode}) instead of 200 (OK). Response: {errorContent}";
                Report.Error(errorMessage);
                throw new HttpRequestException(errorMessage);
            }
            
            var content = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
            return JsonConvert.DeserializeObject<StatusResponse>(content);
        }

        public async Task SetPosition(int? tilt, int? angle)
        {
            Report.Info($"TurntableRestClient::SetPosition - Tilt: {tilt}, Angle: {angle}");
            var payload = new Dictionary<string, int>();
            if (tilt.HasValue)
            {
                payload["tilt"] = tilt.Value;
            }
            if (angle.HasValue)
            {
                payload["angle"] = angle.Value;
            }

            var json = JsonConvert.SerializeObject(payload);
            Report.Info($"TurntableRestClient::SetPosition - Sending JSON: {json}");
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var response = await _client.PutAsync($"{_baseUrl}/position", content).ConfigureAwait(false);
            
            if (response.StatusCode != System.Net.HttpStatusCode.OK)
            {
                var errorContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                string errorMessage = $"TurntableRestClient::SetPosition - Server returned status code {(int)response.StatusCode} ({response.StatusCode}) instead of 200 (OK). Response: {errorContent}";
                Report.Error(errorMessage);
                throw new HttpRequestException(errorMessage);
            }
        }

        public async Task Reset()
        {
            Report.Info("TurntableRestClient::Reset");
            var response = await _client.PostAsync($"{_baseUrl}/reset", null).ConfigureAwait(false);
            
            if (response.StatusCode != System.Net.HttpStatusCode.OK)
            {
                var errorContent = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                string errorMessage = $"TurntableRestClient::Reset - Server returned status code {(int)response.StatusCode} ({response.StatusCode}) instead of 200 (OK). Response: {errorContent}";
                Report.Error(errorMessage);
                throw new HttpRequestException(errorMessage);
            }
        }
    }

    public class StatusResponse
    {
        public int Angle { get; set; }
        public int Tilt { get; set; }
        public bool Connected { get; set; }
    }
}

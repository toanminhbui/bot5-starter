// Minimal local controller example. It holds the actual reset joint angles;
// this demonstrates the API rather than a trained or qualified fighting bot.
#include "unified/plugin_api.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace {
class PdHold final : public arena_common::JointController {
 public:
  explicit PdHold(const nlohmann::json& configuration) {
    if (!configuration.is_object()) throw std::invalid_argument("PD configuration must be an object");
    for (const auto& [name, value] : configuration.items()) {
      (void)value;
      if (name != "kp" && name != "kd") throw std::invalid_argument("Unknown PD configuration field");
    }
    kp_ = configuration.value("kp", 40.);
    kd_ = configuration.value("kd", 8.);
    if (!std::isfinite(kp_) || !std::isfinite(kd_) || kp_ < 0. || kd_ < 0.)
      throw std::invalid_argument("PD gains must be finite and nonnegative");
  }

  std::string build_identity() const override { return "example_pd_hold_v1"; }

  void reset(std::uint64_t seed, int side, std::span<const arena_common::JointState> joints) override {
    (void)seed;
    if (side != 0 && side != 1) throw std::invalid_argument("Invalid fighter side");
    side_ = side;
    names_.clear();
    references_.clear();
    for (const auto& joint : joints) {
      if (!std::isfinite(joint.position_rad)) throw std::invalid_argument("Nonfinite reset joint");
      names_.push_back(joint.name);
      references_.push_back(joint.position_rad);
    }
  }

  std::vector<double> joint_torques(const arena_common::ControllerInput& input) override {
    if (input.side != side_ || input.owned_joints.size() != references_.size())
      throw std::invalid_argument("PD controller received another fighter's joints");
    std::vector<double> torques;
    torques.reserve(references_.size());
    for (std::size_t i = 0; i < references_.size(); ++i) {
      const auto& joint = input.owned_joints[i];
      if (joint.name != names_[i] || !std::isfinite(joint.position_rad) ||
          !std::isfinite(joint.velocity_rad_s) || !std::isfinite(joint.maximum_torque_Nm) ||
          joint.maximum_torque_Nm < 0.) throw std::invalid_argument("Invalid owned joint state");
      const double requested = kp_ * (references_[i] - joint.position_rad) - kd_ * joint.velocity_rad_s;
      if (!std::isfinite(requested)) throw std::invalid_argument("PD torque overflow");
      torques.push_back(std::clamp(requested, -joint.maximum_torque_Nm, joint.maximum_torque_Nm));
    }
    return torques;
  }

 private:
  double kp_ = 40., kd_ = 8.;
  int side_ = -1;
  std::vector<std::string> names_;
  std::vector<double> references_;
};
}

extern "C" std::uint32_t kickbox_controller_abi_version() {
  return arena_unified::controller_plugin_abi_version;
}

extern "C" arena_common::JointController* kickbox_create_joint_controller(const char* configuration_json) {
  return new PdHold(nlohmann::json::parse(configuration_json ? configuration_json : "{}"));
}

extern "C" void kickbox_destroy_joint_controller(arena_common::JointController* controller) {
  delete controller;
}

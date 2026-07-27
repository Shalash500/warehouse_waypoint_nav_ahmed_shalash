import math
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from visualization_msgs.msg import Marker, MarkerArray


class MissionNode(Node):
    def __init__(self):
        super().__init__('warehouse_mission_node')

        self._client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Transient local so RViz gets the last published marker state
        marker_qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._marker_pub = self.create_publisher(MarkerArray, '/waypoint_markers', marker_qos)

        # Named waypoints in the map frame: (x, y, yaw)
        self.waypoints = {
            'home':     (-0.425344, 7.25204, 0.0191374),
            'loading':  (18.5731, 3.78951, -1.57201),
            'storage':  (7.33734, -5.4914, 3.13288),
            'shipping': (-7.10548, 0.737749, 1.57224),
        }

        self.mission_order = ['home', 'loading', 'storage', 'shipping', 'home']
        self.current_index = 0
        self._wait_timer = None

        # Show all four markers (none active yet) before the mission starts
        self.publish_markers(active_name=None)

    def publish_markers(self, active_name):
        marker_array = MarkerArray()
        for i, (name, (x, y, yaw)) in enumerate(self.waypoints.items()):
            marker = Marker()
            marker.header.frame_id = 'map'
            marker.header.stamp = self.get_clock().now().to_msg()
            marker.ns = 'waypoints'
            marker.id = i
            marker.type = Marker.CUBE
            marker.action = Marker.ADD
            marker.pose.position.x = x
            marker.pose.position.y = y
            marker.pose.position.z = 0.15
            marker.pose.orientation.z = math.sin(yaw / 2.0)
            marker.pose.orientation.w = math.cos(yaw / 2.0)
            marker.scale.x = 0.3
            marker.scale.y = 0.3
            marker.scale.z = 0.3
            if name == active_name:
                marker.color.r, marker.color.g, marker.color.b, marker.color.a = 0.0, 1.0, 0.0, 1.0
            else:
                marker.color.r, marker.color.g, marker.color.b, marker.color.a = 0.0, 0.0, 1.0, 1.0
            marker_array.markers.append(marker)

            label = Marker()
            label.header.frame_id = 'map'
            label.header.stamp = marker.header.stamp
            label.ns = 'waypoint_labels'
            label.id = i
            label.type = Marker.TEXT_VIEW_FACING
            label.action = Marker.ADD
            label.pose.position.x = x
            label.pose.position.y = y
            label.pose.position.z = 0.5
            label.scale.z = 0.3
            label.color.r, label.color.g, label.color.b, label.color.a = 1.0, 1.0, 1.0, 1.0
            label.text = name
            marker_array.markers.append(label)

        self._marker_pub.publish(marker_array)

    def start_mission(self):
        self.get_logger().info('Mission started.')
        self.get_logger().info('Waiting for navigate_to_pose action server...')
        self._client.wait_for_server()
        self.send_next_goal()

    def send_next_goal(self):
        if self.current_index >= len(self.mission_order):
            self.get_logger().info('Mission complete: robot is back home.')
            rclpy.shutdown()
            return

        name = self.mission_order[self.current_index]
        x, y, yaw = self.waypoints[name]
        self.publish_markers(active_name=name)

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal_msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f'Navigating to {name}: x={x}, y={y}, yaw={yaw}')

        send_future = self._client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        send_future.add_done_callback(self.goal_response_callback)

    def feedback_callback(self, feedback_msg):
        remaining = feedback_msg.feedback.distance_remaining
        self.get_logger().info(f'Distance remaining: {remaining:.2f} m')

    def goal_response_callback(self, future):
        goal_handle = future.result()
        name = self.mission_order[self.current_index]

        if not goal_handle.accepted:
            x, y, yaw = self.waypoints[name]
            self.get_logger().error(f'Goal to "{name}" was REJECTED. Location: x={x}, y={y}, yaw={yaw}')
            rclpy.shutdown()
            return

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        status = future.result().status
        name = self.mission_order[self.current_index]
        x, y, yaw = self.waypoints[name]

        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f'Navigation to "{name}" FAILED (status={status}). '
                f'Stopping mission. Last target location: x={x}, y={y}, yaw={yaw}')
            rclpy.shutdown()
            return

        self.get_logger().info(f'Reached {name}.')

        if name == 'loading':
            self.get_logger().info('Waiting 30 seconds at Loading Station...')
            self._wait_timer = self.create_timer(30.0, self._loading_wait_done)
        else:
            self.current_index += 1
            self.send_next_goal()

    def _loading_wait_done(self):
        self._wait_timer.cancel()
        self.current_index += 1
        self.send_next_goal()


def main():
    rclpy.init()
    node = MissionNode()
    node.start_mission()
    rclpy.spin(node)


if __name__ == '__main__':
    main()